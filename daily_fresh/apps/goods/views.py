from django.shortcuts import render, redirect
from django.core.urlresolvers import reverse
from django.views.generic import View
from goods.models import GoodsCategory, IndexGoodsBanner, IndexCategoryGoodsBanner, IndexPromotionBanner, GoodsSKU
from django_redis import get_redis_connection
from django.core.cache import cache
from django.core.paginator import Paginator, EmptyPage
import json


# Create your views here.

class BaseView(View):
    def get_cart_number(self, request):
        cart_number = 0
        # 如果用户登录,从redis中获取购物车数据
        if request.user.is_authenticated():
            user_id = request.user.id
            # 获取与redis数据哭的链接
            redis_conn = get_redis_connection("default")
            cart = redis_conn.hgetall("cart_{}".format(user_id))
           
        
        else:
            # 如果用户没有的登录从从cookies中获取数据
            json_cart = request.COOKIES.get("cart")
            
            if json_cart is not None:
                cart = json.loads(json_cart)
            else:
                cart = {}
        for value in cart.values():
            cart_number += int(value)
        
        
        return cart_number


class GoodIndexView(BaseView):
    def get(self, request):
        # 先尝试从缓存中读取数据
        context = cache.get("index_page_data")
        
        # 如果缓存中没有数据，再查询
        
        if context is None:
            print("没有缓存数据， 查询了数据库")
            # 查询数据库，获取需要的数据放到模板中
            
            # 商品分类信息
            categorys = GoodsCategory.objects.all()
            
            # 首页轮播图信息, 按照index进行排序
            index_goods_banners = IndexGoodsBanner.objects.all().order_by("index")
            
            # 活动信息
            promotion_banners = IndexPromotionBanner.objects.all().order_by("index")
            
            # 分类商品信息
            for category in categorys:
                title_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=0).order_by(
                    "index")
                category.title_banners = title_banners
                
                image_banners = IndexCategoryGoodsBanner.objects.filter(category=category, display_type=1).order_by(
                    "index")
                category.image_banners = image_banners
            
            context = {
                "categorys": categorys,
                "index_banners": index_goods_banners,
                "promotion_banners": promotion_banners,
                }
        
        # 设置缓存数据
        #           名字              内容      有效期
        cache.set("index_page_data", context, 3600)
        
        # 购物车数据
        cart_number = self.get_cart_number(request)
        
        # 处理模板
        context.update({"cart_number": cart_number})
        
        return render(request, "index.html", context)


class DetailView(BaseView):
    """商品详细信息页面"""
    
    def get(self, request, sku_id):
        # 尝试获取缓存数据
        context = cache.get("detail_%s" % sku_id)
        # 如果缓存不存在
        if context is None:
            try:
                # 获取商品信息
                sku = GoodsSKU.objects.get(id=sku_id)
            except GoodsSKU.DoesNotExist:
                # from django.http import Http404
                # raise Http404("商品不存在!")
                return redirect(reverse("goods:index"))
            
            # 获取类别
            categorys = GoodsCategory.objects.all()
            
            # 从订单中获取评论信息
            sku_orders = sku.ordergoods_set.all().order_by('-create_time')[:30]
            if sku_orders:
                for sku_order in sku_orders:
                    sku_order.ctime = sku_order.create_time.strftime('%Y-%m-%d %H:%M:%S')
                    sku_order.username = sku_order.order.user.username
            else:
                sku_orders = []
            
            # 获取最新推荐
            new_skus = GoodsSKU.objects.filter(category=sku.category).order_by("-create_time")[:2]
            
            # 获取其他规格的商品
            goods_skus = sku.goods.goodssku_set.exclude(id=sku_id)
            
            context = {
                "categorys": categorys,
                "sku": sku,
                "orders": sku_orders,
                "new_skus": new_skus,
                "goods_skus": goods_skus
                }
            
            # 设置缓存
            cache.set("detail_%s" % sku_id, context, 3600)
        
        # 购物车数量
        cart_number = self.get_cart_number(request)
        # 如果是登录的用户
        if request.user.is_authenticated():
            redis_conn = get_redis_connection("default")
            user_id=request.user.id
            
            # 浏览记录
            # 移除已经存在的本商品浏览记录
            redis_conn.lrem("history_%s" % user_id, 0, sku_id)
            # 添加新的浏览记录
            redis_conn.lpush("history_%s" % user_id, sku_id)
            # 只保存最多5条记录
            redis_conn.ltrim("history_%s" % user_id, 0, 4)
        
        context.update({"cart_number": cart_number})
        
        return render(request, 'detail.html', context)


# 商品列表页视图
class ListView(BaseView):
    def get(self, request, category_id, page):
        # 获取排序方式
        sort = request.GET.get("sort", "default")
        if sort not in ("price", "hot"):
            sort = "default"
        # 根据分类id查询数据库
        try:
            category = GoodsCategory.objects.get(id=category_id)
        except GoodsCategory.DoesNotExist:
            return redirect(reverse("goods:index"))
        # 查询购物车数据
        cart_number = self.get_cart_number(request)
        
        # 查询所有的商品分类
        categorys = GoodsCategory.objects.all()
        # 查询新品推荐
        new_skus = GoodsSKU.objects.filter(category=category).order_by("-create_time")[:2]
        # 分类商品，排序
        if sort == "price":
            skus = GoodsSKU.objects.filter(category=category).order_by("price")
        elif sort == "hot":
            skus = GoodsSKU.objects.filter(category=category).order_by("-sales")
        else:
            skus = GoodsSKU.objects.filter(category=category)
        # 获取当前页数
        page = int(page)
        paginator = Paginator(skus, 2)

        # 获取当前页面数据
        try:
            page_skus = paginator.page(page)
        except EmptyPage:
            page_skus = paginator.page(1)
            page = 1
        # 页数
        """
        总页数小于5页
        总页数大于5页,当前页位于前3页
        总页数大于5页,当前页位于后3页
        其他
        """
        total_page = paginator.num_pages
        if total_page < 5:
            page_list = range(1, total_page + 1)
        elif page <= 3:
            page_list = range(1, 6)
        elif (total_page - page) < 3:
            page_list = range(total_page - 4, total_page + 1)
        else:
            page_list = range(page - 2, page + 3)
        context = {
            "category": category,
            "categorys": categorys,
            "new_skus": new_skus,
            "skus": skus,
            "page_list": page_list,
            "page_skus": page_skus,
            "sort": sort,
            "cart_number": cart_number
            }
        return render(request, "list.html", context)





