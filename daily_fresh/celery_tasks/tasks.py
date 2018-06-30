import os
os.environ["DJANGO_SETTINGS_MODULE"] = "daily_fresh.settings"

# 放到celery服务器上时将注释打开
# import django
#
# django.setup()
from celery import  Celery
from django.core.mail import send_mail
from django.conf import settings
from goods.models import GoodsCategory, IndexGoodsBanner, IndexCategoryGoodsBanner, IndexPromotionBanner
from django.template import  loader
#创建celery应用实例
app=Celery("celery_tasks.tasks",broker="redis://192.168.239.29/6")

#定义任务
@app.task
def send_active_email(to_email,user_name,token):
    subject="欢迎使用天天生鲜"          #主题
    body=""                          #文本邮件体
    sender=settings.EMAIL_FROM       #发件人
    receiver=[to_email]                #接收人
    html_body = '<h1>尊敬的用户 %s, 感谢您注册天天生鲜！</h1>' \
                '<br/><p>请点击此链接激活您的帐号<a href="http://127.0.0.1:8000/users/active/%s">' \
                'http://127.0.0.1:8000/users/active/%s<a></p>' % (user_name, token, token)
    send_mail(subject,body,sender,receiver,html_message=html_body)

@app.task
def generate_static_index_html():
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
    #购物车数量
    cart_number=0
    
    context = {
        "categorys": categorys,
        "index_banners": index_goods_banners,
        "promotion_banners": promotion_banners,
        "cart_number":cart_number
        }
    #获取加载模板
    template=loader.get_template("static_index.html")
    #填充数据
    html_data=template.render(context)
    
    #指明文件路径
    file_path=os.path.join(settings.STATICFILES_DIRS[0],"index.html")
    
    with open(file_path,"w") as f:
        f.write(html_data)
  