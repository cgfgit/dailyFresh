from django.shortcuts import render, redirect
from django.views.generic import View
from utils.views import LoginRequiredMixin, LoginRequiredJsonMixin, TransactionAtomicMixin
from django.core.urlresolvers import reverse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
from users.models import Address
from django.http import JsonResponse
from orders.models import OrderInfo, OrderGoods
from django.utils import timezone
from django.db import transaction
from django.core.paginator import Paginator
from django.core.cache import cache
from alipay import AliPay
from django.conf import settings
import os

# Create your views here.

#下单页面视图
class PlaceOrderView(LoginRequiredMixin,View):
    def post(self,request):
        #接收请求参数
        sku_ids=request.POST.getlist("sku_ids")
        count=request.POST.get("count")
        #校验参数
        if not sku_ids:
            return render(reverse("cart:info"))
        user_id=request.user.id
        #存放商品
        skus=[]
        #商品总数量
        total_count=0
        #商品总金额(不包含运费)
        total_skus_amount=0
        #运费暂时写死：10
        trans_cost=10
        #商品总金额包含运费
        total_amount=0
        #获取与redis数据库的连接
        redis_conn=get_redis_connection("default")
        #判断商品数量是否为None,如果是则商品存放在redis数据库中
        if count is None:
            #获取该用户购物车中所有的商品
            cart=redis_conn.hgetall("cart_{}".format(user_id))
            for sku_id in sku_ids:
                try:
                    sku=GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return render(reverse("cart:info"))
                #获取商品数量
                sku_count=cart.get(sku_id.encode())
                sku_count=int(sku_count)
                sku.count=sku_count
                #获取商品金额
                sku_amount=sku.price * sku_count
                sku.amount=sku_amount
                #将商品加入到列表中
                skus.append(sku)
                #商品总数量
                total_count+=sku_count
                #商品总金额
                total_skus_amount+=sku_amount
                
        else:
            #商品是从详情页过来的
            for sku_id in sku_ids:
                try:
                    sku=GoodsSKU.objects.get(id=sku_id)
                except GoodsSKU.DoesNotExist:
                    return render(reverse("cart:info"))
                try:
                    count=int(count)
                except:
                    return render(reverse("cart:info",args=(sku_id,)))
                
                #判断库存
                if count > sku.stock:
                    return render(reverse("cart:info", args=(sku_id,)))
                #计算商品金额
                sku_amount=sku.price * count
                sku.amount=sku_amount
                sku.count=count
                skus.append(sku)
                total_count+=count
                total_skus_amount+=sku_amount
                
                #将从商品详情页购买商品的数量保存redis数据库中
                redis_conn.hset("cart_{}".format(user_id),sku_id,count)
        total_amount=total_skus_amount+trans_cost
        #获取地址信息
        try:
            address=Address.objects.filter(user=request.user).latest("create_time")
        except:
            address=None
        
        context={
            "skus":skus,
            "total_count":total_count,
            "sku_skus_amount":total_skus_amount,
            "total_amount":total_amount,
            "trans_cost":trans_cost,
            "address":address,
            "sku_ids": ",".join(sku_ids)
            }
        return render(request,"place_order.html",context)
        
#提交订单页面视图
class CommitOrderView(LoginRequiredJsonMixin, TransactionAtomicMixin, View):
    """提交订单"""
    
    def post(self, request):
        # 获取参数
        #  user 地址id  支付方式  商品id  数量(从购物车中获取）
        user = request.user
        address_id = request.POST.get("address_id")
        sku_ids = request.POST.get("sku_ids")  # "1,2,3,4"
        pay_method = request.POST.get("pay_method")
        
        # 校验参数
        if not all([address_id, sku_ids, pay_method]):
            return JsonResponse({"code": 2, "message": "参数缺失"})
        
        # 判断地址是否存在
        try:
            address = Address.objects.get(id=address_id)
        except Address.DoesNotExist:
            return JsonResponse({"code": 3, "message": "地址不存在"})
        
        # 判断支付方式
        pay_method = int(pay_method)
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({"code": 4, "message": "支付方式错误"})
        
        # 判断商品
        sku_ids = sku_ids.split(",")  # ["1", "2"]
        redis_conn = get_redis_connection("default")
        cart = redis_conn.hgetall("cart_%s" % user.id)
        
        # 创建一个订单基本信息表数据
        
        # 自定义的order_id  "20171026111111用户id"
        order_id = timezone.now().strftime("%Y%m%d%H%M%S") + str(user.id)
        print("hello")
        
        # 创建事务保存点
        save_id = transaction.savepoint()
        try:
            order = OrderInfo.objects.create(
                order_id=order_id,
                user=user,
                address=address,
                total_amount=0,
                trans_cost=10,
                pay_method=pay_method,
                )
            
            total_count = 0  # 总数
            total_amount = 0  # 总金额
            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoodsSKU.objects.get(id=sku_id)
                    except GoodsSKU.DoesNotExist:
                        # 回退的保存点的状态
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 5, "message": "商品有误"})
                    
                    # 获取订购的商品数量，判断库存
                    sku_count = cart.get(sku_id.encode())
                    sku_count = int(sku_count)
                    if sku_count > sku.stock:
                        # 回退的保存点的状态
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 6, "message": "库存不足"})
                    
                    # 减少商品的库存, 增加商品的销量
                    origin_stock = sku.stock
                    new_stock = origin_stock - sku_count
                    new_sales = sku.sales + sku_count
                    # update操作会返回受影响的行数，即更新成功的函数
                    result = GoodsSKU.objects.filter(id=sku_id, stock=origin_stock).update(stock=new_stock,
                                                                                           sales=new_sales)
                    if result == 0 and i < 2:
                        # 表示更新失败
                        continue
                    elif result == 0 and i == 2:
                        # 表示尝试三次失败
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({"code": 7, "message": "下单失败"})
                    
                    # 保存订单商品
                    OrderGoods.objects.create(
                        order=order,
                        sku=sku,
                        count=sku_count,
                        price=sku.price,
                        )
                    
                    # 累计计算总数
                    total_count += sku_count
                    # 累计计算总金额
                    total_amount += (sku.price * sku_count)
                    
                    # 跳出三次循环，处理下一个商品
                    break
            
            # 修改订单基本信息表中的统计数据字段
            order.total_count = total_count
            order.total_amount = total_amount + 10
            order.save()
        
        except Exception:
            # 出现任何异常，都要回退的保存点的状态
            transaction.savepoint_rollback(save_id)
            return JsonResponse({"code": 8, "message": "下单失败"})
        # 执行成功，提交事务
        transaction.savepoint_commit(save_id)
        
        # 保存最新的购物车数据
        redis_conn.hdel("cart_%s" % user.id, *sku_ids)  # 删除订购的商品
        
        # 返回前端json状态
        return JsonResponse({"code": 0, "message": "创建订单成功"})
        
#用户订单视图
class UserOrderView(LoginRequiredMixin,View):
    def get(self,request,page):
        print(page,"*"*10)
        #获取当前用户
        user=request.user
        #获取所有的订单
        orders=user.orderinfo_set.all().order_by("-create_time")
        #遍历所有的订单
        for order in orders:
            
            #查询订单的状态
            order.status_name=OrderInfo.ORDER_STATUS[order.status]
            #查看订单的支付方式
            order.pay_method_name=OrderInfo.PAY_METHODS[order.pay_method]

            order.skus = []
            #获取每个订单中所有的商品
            order_skus=order.ordergoods_set.all()
            for order_sku in order_skus:
                sku=order_sku.sku
                sku.count=order_sku.count
                sku.amount=sku.count*sku.price
                order.skus.append(sku)

        # 分页
        paginator = Paginator(orders, 3)
        # 获取页码的列表
        pages = paginator.page_range
        # 获取总页数
        num_pages = paginator.num_pages
        # 当前页转化为数字
        page = int(page)

        # 1.如果总页数<=5
        # 2.如果当前页是前3页
        # 3.如果当前页是后3页,
        # 4.既不是前3页，也不是后3页
        if num_pages <= 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif (num_pages - page) <= 2:
            pages = range(num_pages - 4, num_pages + 1)
        else:
            pages = range(page - 2, page + 3)

        # 取第page页的内容 has_previous has_next number
        page_orders = paginator.page(page)

        context = {
            "orders": page_orders,
            "page": page,
            "pages": pages
            }

        return render(request, "user_center_order.html", context)
        
        
        
