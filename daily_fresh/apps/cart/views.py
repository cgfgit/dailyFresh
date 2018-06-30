from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsCategory, IndexGoodsBanner, IndexCategoryGoodsBanner, IndexPromotionBanner, GoodsSKU
from django_redis import get_redis_connection
import json,ast


# Create your views here.

# 加入购物车视图界面
class AddCartView(View):
    
    def post(self, request):
        
        # 获取请求参数
        # 获取商品id
        sku_id = request.POST.get("sku_id")
        # 获取商品数量
        count = request.POST.get("count")
        # 获取当前用户id
        user_id = request.user.id
        # 校验参数的是否完整
        if not all([sku_id, count]):
            return JsonResponse({"code": 2, "message": "请求参数不完整"})
        
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"code": 3, "message": "该商品不存在"})
        # 判断库存
        try:
            count = int(count)
        except:
            JsonResponse({"code": 4, "message": "参数类型错误"})
        
        # 判断库存
        if count > sku.stock:
            return JsonResponse({"code": 5, "message": "库存不足"})
        
        # 如果用户登录,从redis中获取购物车数据
        if request.user.is_authenticated():
            
            # 获取redis连接对象
            conn = get_redis_connection("default")
            
            # 尝试从该用户的购物车中获取数据
            origin_count = conn.hget("cart_{}".format(user_id), sku_id)
            if origin_count is not None:
                count += int(origin_count)
            conn.hset("cart_{}".format(user_id), sku_id, count)
            
            # 获取该用户购物车总数量
            cart_number = 0
            cart = conn.hgetall("cart_{}".format(user_id))
            for value in cart.values():
                cart_number += int(value)
            
            # 添加数据成功返回数据给前段页面
            return JsonResponse({"code": 0, "message": "加入购物车成功", "cart_number": cart_number})
        else:
            # 该用户没有登录,数据存放在cookies中
            # 先尝试从cookies中获取数据
            cart_json = request.COOKIES.get("cart")
            if cart_json is not None:
                cart = json.loads(cart_json)
            else:
                cart = {}
            if sku_id in cart:
                origin_count = cart.get(sku_id)
                count += origin_count
            cart[sku_id] = count

            # 获取cookies中购物车总数量
            cart_number = 0
            for value in cart.values():
                cart_number += int(value)
            
            response = JsonResponse({"code": 0, "message": "添加购物车成功", "cart_number": cart_number})
            # 将cart转化成json
            new_json_cart = json.dumps(cart)
            # 将数据设置到cookies中
            response.set_cookie("cart", new_json_cart)
            # 返回前端处理数据
            return response


# 购物车信息视图界面
class CartInfoView(View):
   
    def get(self, request):
        # 商品总金额
        total_amount = 0
        # 商品总数量
        total_count = 0
        skus=[]
        
        # 如果用户登录,从redis中获取购物车数据
        if request.user.is_authenticated():
            user_id=request.user.id
            #获取redis连接
            redis_conn=get_redis_connection("default")
            #获取redis数据库购物车中数据
            cart=redis_conn.hgetall("cart_{}".format(user_id))
            
        else:  # 没有登录则从cookies购物车中获取数据
            json_cart = request.COOKIES.get("cart")
            if json_cart is not None:
                cart=json.loads(json_cart)
            else:
                cart={}

        for sku_id, count in cart.items():
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                continue
            # 计算商品小计
            count = int(count)
            amount = sku.price * count
            sku.amount = amount
            sku.count = count
    
            total_amount += amount
            total_count += count
            skus.append(sku)
        #形成前端需要的数据
        context={
            "skus":skus,
            "total_count":total_count,
            "total_amount":total_amount,
            }
        #返回数据给前端
        return render(request,"cart.html",context)
     
     
#更新购物车视图
class UpdateCartView(View):
    def post(self,request):
        #获取商品id
        sku_id=request.POST.get("sku_id")
        #获取商品数量
        count=request.POST.get("count")
        #判断参数是否完整
        if not all([sku_id,count]):
            return  JsonResponse({"code":1,"message":"参数不完整"})
        try:
            sku=GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({"code":2,"message":"没有该商品"})
        try:
            count=int(count)
        except:
            return JsonResponse({"code":3,"message":"参数类型错误"})
        if count > sku.stock:
            return JsonResponse({"code":4,"message":"该商品库存不足"})
        #如果用户登录
        if request.user.is_authenticated():
            #获取redis链接
            redis_conn=get_redis_connection("default")
            user_id=request.user.id
            #设置购物车中数据
            redis_conn.hset("cart_{}".format(user_id),sku_id,count)
            return JsonResponse({"code":0,"message":"更新购物车成功"})
        else:
            #用户没有登录,从cookies中获取购物车数据
            json_cart=request.COOKIES.get("cart")
            if json_cart is not None:
                cart=json.loads(json_cart)
            else:
                cart={}
            cart[sku_id]=count
            response=JsonResponse({"code":0,"message":"更新购物车成功"})
            #更新cookies中数据
            response.set_cookie("cart",json.dumps(cart))
            return response
        
#删除购物车视图
class DeleteCartView(View):
    def post(self,request):
        #获取要删除商品的id
        sku_id=request.POST.get("sku_id")
        #校验参数是否完整
        if not sku_id:
            return JsonResponse({"code":1,"message":"参数不完整"})
        #如果用户没有登录,从cookies中删除数据
        if not request.user.is_authenticated():
            json_cart=request.COOKIES.get("cart")
            if json_cart is not None:
                cart=json.loads(json_cart)
            else:
                cart={}
            if sku_id in cart:
                del cart[sku_id]
                response=JsonResponse({"code":0,"message":"删除数据成功"})
                #更新cookies中数据
                response.set_cookie("cart",json.dumps(cart))
                return response
        #如果用户登录,从redis购物车删除数据
        else:
            redis_conn=get_redis_connection("default")
            redis_conn.hdel("cart_{}".format(request.user.id),sku_id)
            return JsonResponse({"code":0,"message":"删除数据成功"})
            
            
            
        




