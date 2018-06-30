from django.contrib import admin
from goods.models import GoodsCategory, IndexGoodsBanner,IndexPromotionBanner, Goods, GoodsSKU, IndexCategoryGoodsBanner, GoodsImage
from django.contrib import admin
from celery_tasks.tasks import generate_static_index_html
# Register your models here.
class BaseAdmin(admin.ModelAdmin):
    def save_model(self, request, obj, form, change):
        obj.save()
        generate_static_index_html.delay()
        
    def delete_model(self, request, obj):
        obj.save()
        generate_static_index_html.delay()

admin.site.register(GoodsCategory,BaseAdmin)
admin.site.register(IndexPromotionBanner, BaseAdmin)
admin.site.register(GoodsSKU, BaseAdmin)
admin.site.register(Goods, BaseAdmin)
admin.site.register(IndexCategoryGoodsBanner, BaseAdmin)
admin.site.register(GoodsImage, BaseAdmin)
admin.site.register(IndexGoodsBanner, BaseAdmin)