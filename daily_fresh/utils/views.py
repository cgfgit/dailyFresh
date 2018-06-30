from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from functools import  wraps
from django.db import transaction
class LoginRequiredMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
       view=super(LoginRequiredMixin,cls).as_view(**initkwargs)
       return login_required(view)

#验证用户的登录状态
class LoginRequiredJsonMixin(object):
    @classmethod
    def as_view(cls, **initkwargs):
        view = super(LoginRequiredJsonMixin, cls).as_view(**initkwargs)
        return login_required_json(view)


def login_required_json(fun_view):
    @wraps(fun_view)
    def wrapper(request,*args,**kwargs):
        if not request.user.is_authenticated():
            return JsonResponse({"code":1,"message":"用户未登录"})
        else:
            #如果用户登录,则进入到视图函数中执行
            return fun_view(request,*args,**kwargs)
    return wrapper


#提供数据库的事物功能
class TransactionAtomicMixin(object):
    @classmethod
    def as_view(self, **initkwargs):
        view=super(TransactionAtomicMixin, self).as_view(**initkwargs)
        return transaction.atomic(view)

