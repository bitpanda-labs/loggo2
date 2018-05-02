"""
Theoretically we would like to be able to log all function inputs and outputs,
as well as any thrown exceptions, just by decorating a class.
"""
from .loggo import Loggo
def exhaustive(logging_class, config):

    class LoggedClass(object):

        def __init__(self, *args, **kwargs):
            self.original = logging_class(*args,**kwargs)

        def __getattribute__(self,s):
            """
            this is called whenever any attribute of a LoggedClass object is accessed. This function first tries to
            get the attribute off LoggedClass. If it fails then it tries to fetch the attribute from self.original (an
            instance of the decorated class). If it manages to fetch the attribute from self.original, and
            the attribute is an instance method then `Loggo.logme` is applied.
            """
            try:
                x = super(LoggedClass,self).__getattribute__(s)
            except AttributeError:
                pass
            else:
                return x
            x = self.original.__getattribute__(s)

            # special handling for init?
            if type(x) == type(self.__init__): # it is an instance method
                return Loggo(config).logme(x)  # this is equivalent of just decorating the method with Loggo.logme
            else:
                return Loggo(config).logme(x)

    return LoggedClass
