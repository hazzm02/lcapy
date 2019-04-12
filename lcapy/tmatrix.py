from .matrix import Matrix
from .laplace import laplace_transform

class tMatrix(Matrix):
    from .texpr import tExpr    
    _typewrap = tExpr    

    def laplace(self):

        def lt(expr):
            from .sym import ssym, tsym
            return laplace_transform(expr, tsym, ssym)
        
        return sMatrix(self.applyfunc(lt))
    
from .smatrix import sMatrix
