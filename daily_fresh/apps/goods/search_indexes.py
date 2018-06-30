from haystack import indexes
from goods.models import GoodsSKU
#对某个类某些字段建立索引
class GoodsSKUIndex(indexes.SearchIndex,indexes.Indexable):
    text=indexes.CharField(document=True,use_template=True)
    def get_model(self):
        return GoodsSKU
    def index_queryset(self, using=None):
        return self.get_model().objects.all()
    