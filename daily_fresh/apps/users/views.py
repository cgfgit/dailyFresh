from django.shortcuts import render,HttpResponse,redirect
from django.core.urlresolvers import reverse
from django.views.generic import  View
from users.models import User
import re
from django import db
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from django.conf import settings
from itsdangerous import SignatureExpired
from celery_tasks.tasks import send_active_email
from django.contrib.auth import authenticate,login,logout
from utils.views import LoginRequiredMixin
from users.models import Address
from goods.models import GoodsSKU
from django_redis import get_redis_connection
import json

# Create your views here.

#用户注类视图
class RegisterView(View):
    def get(self,request):
        return render(request,"register.html")
    def post(self,request):
        #获取请求参数
        username=request.POST.get("user_name")
        password=request.POST.get("pwd")
        email=request.POST.get("email")
        allow=request.POST.get("allow")
        #校验参数完整性
        if not all([username,password,email]):          #如果参数不完整,仍然停留在登录页面
            return redirect(reverse("users:register"))
            
        #校验参数
        #对邮箱进行校验
        if not re.match(r"^[a-z0-9][\w\.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$",email):
            return render(request,"register.html",{"email_errmsg":"邮箱格式不正确"})
        
        if "on" != allow:
            render(request,"register.html",{"allow_errmsg":"请勾选同意协议"})
            
        #进行业务逻辑处理,将用户保存到数据库
            """
                对密码进行加密
                将用户保存到数据库    user=User()
                                    user.save()
                用户自定义模型已经做好
            """
        try:            #用户名重复注册问题
            user=User.objects.create_user(username,email,password)
        except db.IntegrityError:
            return render(request,"register.html",{"user_errmsg":"该用户已经被注册"})
        #将用户设置成未激活状态
        user.is_active=False
        user.save()
        
        #获取token发送邮件
        token=user.generate_active_token()
        #发送邮件
        send_active_email.delay(email,username,token)
        
        #返回视图给前端
        return redirect("goods:index")
    
#邮件激活视图
class ActiveView(View):
    def get(self,request,token):
        #获取序列化器
        serializer = Serializer(settings.SECRET_KEY, 3600)
        """生成激活令牌"""
        try:
            result=serializer.loads(token)
        except  SignatureExpired:
            return  HttpResponse("该连接已经过期")
        
        user_id=result.get("confirm")
        try:
            user=User.objects.get(id=user_id)
        except User.DoesNotExist:
            return HttpResponse("该用户不存在")
        
        #将用户设置激活状态
        user.is_active=True
        user.save()
        
        #返回前端界面
        return redirect(reverse("users:login"))
        
#用户登录模块
class LoginView(View):
    def get(self,request):
        return render(request,"login.html")
    def post(self,request):
        #接收请求参数
        username=request.POST.get("username")
        password=request.POST.get("pwd")
        remembered=request.POST.get("remembered")
        #对请求参数进行校验
        if not all([username,password]):
            #参数不完整，返回到登录页面
            print("*"*100)
            return redirect(reverse("users:login"))
        #进行数据库的业务处理功能,判断该用户是否存在
        """
            对用户的密码进行加密,根据用户名和密码进行查询
            user=User.objects.filter(username=username,password=password)
        """
        #使用Django用户认证系统
        user=authenticate(username=username,password=password)
        if user is None:
            return render(request,"login.html",{"errmsg":"用户名或密码错误"})
        #用户是否激活
        if user.is_active==False:
            return render(request,"login.html",{"errmsg":"该用户尚未激活"})
        #将用户的登录状态保存到session中
        login(request,user)
        if remembered !="on":           #没有勾选用户名，将session中设置临时有效
            request.session.set_expiry(0)
        else:                           #勾选用户名,保存用户的登录状态       默认１４天
            request.session.set_expiry(None)
            
            
        #在用户登录时候需要将cookies中的购物车数据和redis中购物车数据进行合并
        redis_conn=get_redis_connection("default")
        #获取redis中购物车数据
        cart_redis=redis_conn.hgetall("cart_{}".format(request.user.id))
        print(cart_redis,"*"*100)
        #获取cookies中购物车数据
        json_cart_cookies=request.COOKIES.get("cart")
        if json_cart_cookies is not None:
            cart_cookies=json.loads(json_cart_cookies)
            for sku_id,count in cart_cookies.items():
                sku_id=sku_id.encode()
                if sku_id in cart_redis:
                    origin_count=cart_redis.get(sku_id)
                    count+=int(origin_count)
                cart_redis[sku_id]=count
            #将合并的购物车数据保存到redis中
            redis_conn.hmset("cart_{}".format(request.user.id),cart_redis)
            
        
        
        #判读路径中是否携带next参数
        next=request.GET.get("next")
        if next is None:            #如果没有next参数跳转到首页
            response= redirect(reverse("goods:index"))
        else:
            response= redirect(next)          #跳转到next页面
         # 清除cookies中购物车中数据

        response.delete_cookie("cart")
            
        return response
    
#用户退出
class LogoutView(View):
    def get(self,request):
        #用户退出时,需要将session数据删除,Django认证系统已经帮我们实现好了
        logout(request)
        return redirect(reverse("goods:index"))

#用户地址视图(涉及到指定的用户所以用户必须登录)
class UserAddressView(LoginRequiredMixin,View):
    def get(self,request):
        #获取当前登录的用户
        user=request.user
        #根据用户查询地址
        try:
            address=user.address_set.latest("create_time")
        except Address.DoesNotExist:
            address=None
        context={
            "address":address
            }
        return render(request,"user_center_site.html",context)
    def post(self,request):
        #获取当前用户
        user=request.user
        #获取请求参数
        recv_name=request.POST.get("recv_name")
        addr=request.POST.get("addr")
        zip_code=request.POST.get("zip_code")
        recv_mobile=request.POST.get("recv_mobile")
        
        #对请求参数进行校验
        if not all([recv_name,addr,zip_code,recv_mobile]):
            return redirect(reverse("users:address"))
        #对数据库进行操作,创建地址并保存
        address=Address.objects.create(
            user=user,
            receiver_name=recv_name,
            receiver_mobile=recv_mobile,
            detail_addr=addr,
            zip_code=zip_code,
            
            )
        context={
            "address":address
            }
        #跳转页面
        return render(request,"user_center_site.html",context)
        
class UserInfoView(LoginRequiredMixin,View):
    def get(self,request):
        #获取当前用户
        user=request.user
        #获取用户用户地址
        try:
            address=user.address_set.latest("create_time")
        except Address.DoesNotExist:
            address=None
        #从django-redis中获取redis的链接
        conn=get_redis_connection("default")
        #获取历史记录中的所有商品的id
        sku_ids=conn.lrange("history_{}".format(user.id),0,4)
        
        #skus存放从数据库中查询到所有的商品
        skus=[]
        #遍历商品sku_ids,从数据库中获取对应的商品
        for sku_id in sku_ids:
            sku=GoodsSKU.objects.get(id=sku_id)
            skus.append(sku)
        context={
            "address":address,
            "skus":skus
            }
        #返回对应的前段页面
        return render(request,"user_center_info.html",context)
        
        