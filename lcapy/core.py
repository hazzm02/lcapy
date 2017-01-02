"""
This module provides the core functions and classes for Lcapy.

To print the rational functions in canonical form (with the highest
power of s in the denominator with a unity coefficient), use
print(x.canonical()).

For additional documentation, see the Lcapy tutorial.

Copyright 2014, 2015, 2016 Michael Hayes, UCECE
"""

from __future__ import division
from lcapy.latex import latex_str
from lcapy.acdc import is_dc, is_ac, is_causal, ACChecker
from lcapy.sympify import canonical_name, sympify1, symbols_find
from ratfun import Ratfun, _zp2tf
from lcapy.laplace import laplace_transform, inverse_laplace_transform
from lcapy.fourier import fourier_transform, inverse_fourier_transform
import numpy as np
from sympy.assumptions.assume import global_assumptions
import sympy as sym
import re
from sympy.utilities.lambdify import lambdify
import sys
from copy import copy
import six


# Note imports at bottom to avoid circular dependencies

# TODO, propagate assumptions for arithmetic.........  This may be
# tricky.  At the moment only a limited propagation of assumptions are
# performed.

__all__ = ('pprint', 'pretty', 'latex', 'DeltaWye', 'WyeDelta', 'tf',
           'symbol', 'sympify',
           'zp2tf', 'Expr', 's', 'sExpr', 't', 'tExpr', 'f', 'fExpr', 'cExpr',
           'omega', 'omegaExpr', 'Phasor',
           'pi', 'cos', 'sin', 'tan', 'atan', 'atan2',
           'exp', 'sqrt', 'log', 'log10', 'gcd', 'oo', 'inf',
           'H', 'Heaviside', 'DiracDelta', 'j', 'u', 'delta',
           'Vector', 'Matrix', 'VsVector', 'IsVector', 'YsVector', 'ZsVector',
           'Hs', 'Is', 'Vs', 'Ys', 'Zs',
           'Ht', 'It', 'Vt', 'Yt', 'Zt',
           'Hf', 'If', 'Vf', 'Yf', 'Zf',
           'Iphasor', 'Vphasor', 'In', 'Vn',
           'Vconst', 'Iconst', 'Isuper', 'Vsuper',
           'Homega', 'Iomega', 'Vomega', 'Yomega', 'Zomega')

func_pattern = re.compile(r"\\operatorname{(.*)}")

from sympy.printing.str import StrPrinter
from sympy.printing.latex import LatexPrinter
from sympy.printing.pretty.pretty import PrettyPrinter

class LcapyStrPrinter(StrPrinter):

    def _print(self, expr):

        if hasattr(expr, 'expr'):
            expr = expr.expr

        if expr == sym.I:
            return "j"
        return super(LcapyStrPrinter, self)._print(expr)


class LcapyLatexPrinter(LatexPrinter):

    def _print(self, expr):

        if hasattr(expr, 'expr'):
            expr = expr.expr

        if expr == sym.I:
            return "j"
        return super(LcapyLatexPrinter, self)._print(expr)


def latex(expr, **settings):
    return LcapyLatexPrinter(settings).doprint(expr)


class LcapyPrettyPrinter(PrettyPrinter):

    def _print(self, expr):

        if hasattr(expr, 'expr'):
            expr = expr.expr

        if expr == sym.I:
            return self._print_basestring("j")
        return super(LcapyPrettyPrinter, self)._print(expr)


def pretty(expr, **settings):
    return LcapyPrettyPrinter(settings).doprint(expr)


def uppercase_name(name):

    return name[0].upper() + name[1:]


class Context(object):

    def __init__(self):
        self.symbols = {}
        self.assumptions = {}
        self.previous = None

    def new(self):

        new_context = Context()
        new_context.symbols.update(self.symbols)
        new_context.assumptions.update(self.assumptions)
        return new_context

    def switch(self):

        global context

        self.previous = context
        context = self
        global_assumptions.clear()
        global_assumptions.update(self.assumptions)

    def restore(self):

        if self.previous is None:
            return

        self.assumptions.update(global_assumptions)
        global_assumptions.clear()
        global_assumptions.update(self.previous.assumptions)


def sympify(expr, evaluate=True, **assumptions):
    """Create a sympy expression."""

    return sympify1(expr, context.symbols,
                    evaluate, **assumptions)

def symbol(name, **assumptions):

    return sympify(name, **assumptions)


global_context = Context()
context = global_context

ssym = symbol('s')
tsym = symbol('t', real=True)
fsym = symbol('f', real=True)
omegasym = symbol('omega', real=True)


class Exprdict(dict):

    """Decorator class for dictionary created by sympy"""

    def pprint(self):
        """Pretty print"""

        return pprint(self)

    def latex(self):
        """Latex"""

        return latex_str(latex(self))

    def _repr_pretty_(self, p, cycle):

        p.text(pretty(self))


class Expr(object):

    """Decorator class for sympy classes derived from sympy.Expr"""

    one_sided = False

    # Perhaps have lookup table for operands to determine
    # the resultant type?  For example, Vs / Vs -> Hs
    # Vs / Is -> Zs,  Is * Zs -> Vs

    def __init__(self, arg, **assumptions):

        if isinstance(arg, Expr):
            if assumptions == {}:
                assumptions = arg.assumptions
            arg = arg.expr

        # Perhaps could set dc.
        if arg == 0:
            assumptions['causal'] = True

        # There are two types of assumptions.
        #   1. There are the sympy assumptions that are only associated
        #      with symbols, for example, real=True.
        #   2. The expr assumptions such as dc, ac, causal.  These
        #      are primarily to help the inverse Laplace transform for sExpr
        #      classes.  The omega assumption is required for Phasors.

        self.assumptions = assumptions
        self.expr = sympify(arg, **assumptions)

    def infer_assumptions(self):
        self.assumptions['dc'] = None
        self.assumptions['ac'] = None
        self.assumptions['causal'] = None

    @property
    def is_dc(self):
        if 'dc' not in self.assumptions:
            self.infer_assumptions()
        return self.assumptions['dc'] == True

    @property
    def is_ac(self):
        if 'ac' not in self.assumptions:
            self.infer_assumptions()
        return self.assumptions['ac'] == True

    @property
    def is_causal(self):
        if 'causal' not in self.assumptions:
            self.infer_assumptions()
        return self.assumptions['causal'] == True

    @property
    def is_complex(self):
        if 'complex' not in self.assumptions:
            return False
        return self.assumptions['complex']  == True

    @property
    def val(self):
        """Return floating point value of expression if it can be evaluated,
        otherwise the expression"""

        return self.evalf()

    @property
    def omega(self):
        """Return angular frequency"""

        if 'omega' not in self.assumptions:
            return omega
        return self.assumptions['omega']

    def __hash__(self):
        # This is needed for Python3 so can create a dict key,
        # say for subs.
        return hash(self.expr)

# This will allow sym.sympify to magically extract the sympy expression
# but it will also bypass our __rmul__, __radd__, etc. methods that get called
# when sympy punts.
#
#    def _sympy_(self):
#        # This is called from sym.sympify
#        return self.expr

    def __getattr__(self, attr):

        # This gets called if there is no explicit attribute attr for
        # this instance.  We call the method of the wrapped sympy
        # class and rewrap the returned value if it is a sympy Expr
        # object.

        # FIXME.  This propagates the assumptions.  There is a
        # possibility that the operation may violate them.

        expr = self.expr
        if hasattr(expr, attr):
            a = getattr(expr, attr)

            # If it is not callable, directly wrap it.
            if not hasattr(a, '__call__'):
                if not isinstance(a, sym.Expr):
                    return a
                if hasattr(self, 'assumptions'):
                    return self.__class__(ret, **self.assumptions)
                return self.__class__(ret)

            # If it is callable, create a function to pass arguments
            # through and wrap its return value.
            def wrap(*args):
                """This is wrapper for a SymPy function.
                For help, see the SymPy documentation."""

                ret = a(*args)

                if not isinstance(ret, sym.Expr):
                    return ret

                # Wrap the return value
                if hasattr(self, 'assumptions'):
                    return self.__class__(ret, **self.assumptions)
                return self.__class__(ret)

            return wrap

        # Try looking for a sympy function with the same name,
        # such as sqrt, log, etc.
        # On second thoughts, this may confuse the user since
        # we will pick up methods such as laplace_transform.
        # Perhaps should have a list of allowable functions?
        if True or not hasattr(sym, attr):
            raise AttributeError(
                "%s has no attribute %s." % (self.__class__.__name__, attr))

        def wrap1(*args):

            ret = getattr(sym, attr)(expr, *args)
            if not isinstance(ret, sym.Expr):
                return ret

            # Wrap the return value
            return self.__class__(ret)

        return wrap1

    def __str__(self):

        return LcapyStrPrinter().doprint(self.expr)

    def __repr__(self):

        return '%s(%s)' % (self.__class__.__name__, self.expr)

    def _repr_pretty_(self, p, cycle):

        p.text(pretty(self.expr))

    def _repr_latex_(self):

        return '$%s$' % latex_str(self.latex())

    def __abs__(self):
        """Absolute value"""

        return self.__class__(abs(self.expr), **self.assumptions)

    def __neg__(self):
        """Negation"""

        return self.__class__(-self.expr, **self.assumptions)

    def __compat_mul__(self, x, op):
        """Check if args are compatible and if so return compatible class."""

        # Could also convert Vs / Zs -> Is, etc.
        # But, what about (Vs * Vs) / (Vs * Is) ???

        assumptions = {}
        
        cls = self.__class__
        if not isinstance(x, Expr):
            return cls, self, cls(x), assumptions

        xcls = x.__class__

        if isinstance(self, sExpr) and isinstance(x, sExpr):
            if self.is_causal or x.is_causal:
                assumptions = {'causal' : True}
            elif self.is_dc and x.is_dc:
                assumptions = self.assumptions
            elif self.is_ac and x.is_ac:
                assumptions = self.assumptions
            elif self.is_ac and x.is_dc:
                assumptions = {'ac' : True}
            elif self.is_dc and x.is_ac:
                assumptions = {'ac' : True}                

        if cls == xcls:
            return cls, self, cls(x), assumptions

        # Allow omega * t but treat as t expression.
        if isinstance(self, omegaExpr) and isinstance(x, tExpr):
            return xcls, self, x, assumptions
        if isinstance(self, tExpr) and isinstance(x, omegaExpr):
            return cls, self, x, assumptions                    
        
        if xcls in (Expr, cExpr):
            return cls, self, cls(x), assumptions

        if cls in (Expr, cExpr):
            return xcls, self, x, assumptions

        if isinstance(x, cls):
            return xcls, self, cls(x), assumptions

        if isinstance(self, xcls):
            return cls, self, cls(x), assumptions

        if isinstance(self, tExpr) and isinstance(x, tExpr):
            return cls, self, cls(x), assumptions

        if isinstance(self, sExpr) and isinstance(x, sExpr):
            return cls, self, cls(x), assumptions

        if isinstance(self, omegaExpr) and isinstance(x, omegaExpr):
            return cls, self, cls(x), assumptions

        raise ValueError('Cannot combine %s(%s) with %s(%s) for %s' %
                         (cls.__name__, self, xcls.__name__, x, op))

    def __compat_add__(self, x, op):

        # Disallow Vs + Is, etc.

        assumptions = {}

        cls = self.__class__
        if not isinstance(x, Expr):
            return cls, self, cls(x), assumptions

        xcls = x.__class__

        if isinstance(self, sExpr) and isinstance(x, sExpr):
            if self.assumptions == x.assumptions:
                assumptions = self.assumptions
        
        if cls == xcls:
            return cls, self, x, assumptions

        # Handle Vs + sExpr etc.
        if isinstance(self, xcls):
            return cls, self, x, assumptions

        # Handle sExpr + Vs etc.
        if isinstance(x, cls):
            return xcls, self, cls(x), assumptions

        if xcls in (Expr, cExpr):
            return cls, self, x, assumptions

        if cls in (Expr, cExpr):
            return xcls, cls(self), x, assumptions

        raise ValueError('Cannot combine %s(%s) with %s(%s) for %s' %
                         (cls.__name__, self, xcls.__name__, x, op))

    def __rdiv__(self, x):
        """Reverse divide"""

        cls, self, x, assumptions = self.__compat_mul__(x, '/')
        return cls(x.expr / self.expr, **assumptions)

    def __rtruediv__(self, x):
        """Reverse true divide"""

        cls, self, x, assumptions = self.__compat_mul__(x, '/')
        return cls(x.expr / self.expr, **assumptions)

    def __mul__(self, x):
        """Multiply"""

        cls, self, x, assumptions = self.__compat_mul__(x, '*')
        return cls(self.expr * x.expr, **assumptions)

    def __rmul__(self, x):
        """Reverse multiply"""

        cls, self, x, assumptions = self.__compat_mul__(x, '*')
        return cls(self.expr * x.expr, **assumptions)

    def __div__(self, x):
        """Divide"""

        cls, self, x, assumptions = self.__compat_mul__(x, '/')
        return cls(self.expr / x.expr, **assumptions)

    def __truediv__(self, x):
        """True divide"""

        cls, self, x, assumptions = self.__compat_mul__(x, '/')
        return cls(self.expr / x.expr, **assumptions)

    def __add__(self, x):
        """Add"""

        cls, self, x, assumptions = self.__compat_add__(x, '+')
        return cls(self.expr + x.expr, **assumptions)

    def __radd__(self, x):
        """Reverse add"""

        cls, self, x, assumptions = self.__compat_add__(x, '+')
        return cls(self.expr + x.expr, **assumptions)

    def __rsub__(self, x):
        """Reverse subtract"""

        cls, self, x, assumptions = self.__compat_add__(x, '-')
        return cls(x.expr - self.expr, **assumptions)

    def __sub__(self, x):
        """Subtract"""

        cls, self, x, assumptions = self.__compat_add__(x, '-')
        return cls(self.expr - x.expr, **assumptions)

    def __pow__(self, x):
        """Pow"""

        # TODO: FIXME
        cls, self, x, assumptions = self.__compat_mul__(x, '**')
        return cls(self.expr ** x.expr, **assumptions)

    def __or__(self, x):
        """Parallel combination"""

        return self.parallel(x)

    def __eq__(self, x):
        """Equality"""

        # Note, this is used by the in operator.

        if x is None:
            return False

        cls, self, x, assumptions = self.__compat_add__(x, '==')
        x = cls(x)

        # This fails if one of the operands has the is_real attribute
        # and the other doesn't...
        return self.expr == x.expr

    def __ne__(self, x):
        """Inequality"""

        if x is None:
            return True

        cls, self, x, assumptions = self.__compat_add__(x, '!=')
        x = cls(x)

        return self.expr != x.expr

    def __gt__(self, x):
        """Greater than"""

        if x is None:
            return True

        cls, self, x, assumptions = self.__compat_add__(x, '>')
        x = cls(x)

        return self.expr > x.expr

    def __ge__(self, x):
        """Greater than or equal"""

        if x is None:
            return True

        cls, self, x, assumptions = self.__compat_add__(x, '>=')
        x = cls(x)

        return self.expr >= x.expr

    def __lt__(self, x):
        """Less than"""

        if x is None:
            return True

        cls, self, x, assumptions = self.__compat_add__(x, '<')
        x = cls(x)

        return self.expr < x.expr

    def __le__(self, x):
        """Less than or equal"""

        if x is None:
            return True

        cls, self, x, assumptions = self.__compat_add__(x, '<=')
        x = cls(x)

        return self.expr <= x.expr

    def parallel(self, x):
        """Parallel combination"""

        cls, self, x, assumptions = self.__compat_add__(x, '|')
        x = cls(x)

        return cls(self.expr * x.expr / (self.expr + x.expr), **assumptions)

    def _pretty(self, *args, **kwargs):
        """Make pretty string"""

        # This works in conjunction with Printer._print
        # It is a hack to allow printing of _Matrix types
        # and its elements.
        expr = self.expr
        printer = args[0]

        return printer._print(expr)

    def _latex(self, *args, **kwargs):
        """Make latex string"""

        # This works in conjunction with LatexPrinter._print
        # It is a hack to allow printing of _Matrix types
        # and its elements.
        expr = self.expr
        printer = args[0]

        string = printer._print(expr)
        # sympy uses theta for Heaviside , use u(t) although I prefer H(t)
        string = string.replace(r'\theta\left', r'u\left')

        return string

    def pretty(self):
        """Make pretty string"""
        return pretty(self.expr)

    def prettyans(self, name):
        """Make pretty string with LHS name"""

        return pretty(sym.Eq(sympify(name), self.expr))

    def pprint(self):
        """Pretty print"""
        pprint(self)

    def pprintans(self, name):
        """Pretty print string with LHS name"""
        print(self.prettyans(name))

    def latex(self):
        """Make latex string"""

        string = latex(self.expr)
        match = func_pattern.match(string)
        if match is not None:
            # v_1(t) -> \operatorname{v\_1}\left( t \right)
            # operatorname requires amsmath so switch to mathrm
            string = r'\mathrm{%s}' % match.groups()[0].replace('\\_', '_')

        # sympy uses theta for Heaviside
        string = string.replace(r'\theta\left', r'u\left')
        return latex_str(string)

    def latexans(self, name):
        """Print latex string with LHS name"""

        expr = sym.Eq(sympify(name), self.expr)

        return latex_str(latex(expr))

    @property
    def conjugate(self):
        """Return complex conjugate"""

        return self.__class__(sym.conjugate(self.expr))

    @property
    def real(self):
        """Return real part"""

        dst = self.__class__(sym.re(self.expr).simplify())
        dst.part = 'real'
        return dst

    @property
    def imag(self):
        """Return imaginary part"""

        dst = self.__class__(sym.im(self.expr).simplify())
        dst.part = 'imaginary'
        return dst

    @property
    def real_imag(self):
        """Rewrite as x + j * y"""

        return self.real + j * self.imag

    @property
    def _ratfun(self):
        return Ratfun(self.expr, self.var)

    @property
    def N(self):
        """Return numerator of rational function"""

        return self.numerator

    @property
    def D(self):
        """Return denominator of rational function"""

        return self.denominator

    @property
    def numerator(self):
        """Return numerator of rational function"""

        return self.__class__(self._ratfun.numerator)

    @property
    def denominator(self):
        """Return denominator of rational function"""

        return self.__class__(self._ratfun.denominator)

    def rationalize_denominator(self):
        """Rationalize denominator by multiplying numerator and denominator by
        complex conjugate of denominator"""

        N = self.N
        D = self.D
        Dconj = D.conjugate
        Nnew = (N * Dconj).simplify()
        #Dnew = (D * Dconj).simplify()
        Dnew = (D.real**2 + D.imag**2).simplify()

        Nnew = Nnew.real_imag

        return Nnew / Dnew

    @property
    def magnitude(self):
        """Return magnitude"""

        if self.is_real:
            dst = self
        else:
            R = self.rationalize_denominator()
            N = R.N
            Dnew = R.D
            Nnew = sqrt((N.real**2 + N.imag**2).simplify())
            dst = Nnew / Dnew

        dst.part = 'magnitude'
        return dst

    @property
    def abs(self):
        """Return magnitude"""

        return self.magnitude

    @property
    def dB(self):
        """Return magnitude in dB"""

        # Need to clip for a desired dynamic range?
        # Assume reference is 1.
        dst = 20 * log10(self.magnitude)
        dst.part = 'magnitude'
        dst.units = 'dB'
        return dst

    @property
    def phase(self):
        """Return phase in radians"""

        if self.is_real:
            return 0

        R = self.rationalize_denominator()
        N = R.N

        G = gcd(N.real, N.imag)
        new = N / G
        dst = atan2(new.imag, new.real)
        dst.part = 'phase'
        dst.units = 'rad'
        return dst

    @property
    def phase_degrees(self):
        """Return phase in degrees"""

        dst = self.phase * 180.0 / pi
        dst.part = 'phase'
        dst.units = 'degrees'
        return dst

    @property
    def angle(self):
        """Return phase"""

        return self.phase

    @property
    def is_number(self):

        return self.expr.is_number

    @property
    def is_constant(self):

        return self.expr.is_constant()

    def evaluate(self, arg=None):
        """Evaluate expression at arg.  arg may be a scalar, or a vector.
        The result is of type float or complex.

        There can be no symbols in the expression except for the variable.
        """

        if hasattr(self, 'var'):
            # Use symbol names to avoid problems with symbols of the same
            # name with different assumptions.
            varname = self.var.name
            free_symbols = set([symbol.name for symbol in self.expr.free_symbols])
            if varname in free_symbols:
                free_symbols -= set((varname, ))
            if free_symbols != set():
                raise ValueError('Undefined symbols %s in expression %s' % (tuple(free_symbols), self))

            if arg is None:
                if self.expr.find(self.var) != set():
                    raise ValueError('Need value to evaluate expression at')
                # The arg is irrelevant since the expression is a constant.
                arg = 0
        else:
            arg = 0

        # Perhaps should check if expr.args[1] == Heaviside('t') and not
        # evaluate if t < 0?

        def exp(arg):

            # Hack to handle exp(-a * t) * Heaviside(t) for t < 0
            # by trying to avoid inf when number overflows float.
            if arg > 500:
                arg = 500;
            return np.exp(arg)

        def dirac(arg):

            return np.inf if arg == 0.0 else 0.0

        def heaviside(arg):

            return 1.0 if arg >= 0.0 else 0.0

        def sqrt(arg):

            if arg < 0:
                return 1j * np.sqrt(-arg)
            return np.sqrt(arg)

        # For negative arguments, np.sqrt will return Nan.
        # np.lib.scimath.sqrt converts to complex but cannot be used
        # for lamdification!
        func = lambdify(self.var, self.expr,
                        ({'DiracDelta' : dirac,
                          'Heaviside' : heaviside,
                          'sqrt' : sqrt, 'exp' : exp},
                        "numpy", "sympy", "math"))

        if np.isscalar(arg):
            v1 = arg
        else:
            v1 = arg[0]

        try:
            result = func(v1)
            response = complex(result)
        except NameError:
            raise RuntimeError('Cannot evaluate expression %s' % self)
        except (AttributeError, TypeError):
            if self.expr.is_Piecewise:
                raise RuntimeError(
                    'Cannot evaluate expression %s,'
                    ' due to undetermined conditional result' % self)

            raise RuntimeError(
                'Cannot evaluate expression %s,'
                ' probably have a mysterious function' % self)

        if np.isscalar(arg):
            if np.allclose(response.imag, 0.0):
                response = response.real
            return response

        try:
            response = np.array([complex(func(v1)) for v1 in arg])
        except TypeError:
            raise TypeError(
                'Cannot evaluate expression %s,'
                ' probably have undefined symbols' % self)

        if np.allclose(response.imag, 0.0):
            response = response.real
        return response

    def has(self, subexpr):
        """Test whether the sub expression is contained"""
        if hasattr(subexpr, 'expr'):
            subexpr = subexpr.expr
        return self.expr.has(subexpr)

    def _subs1(self, old, new, **kwargs):

        # This will fail if a variable has different attributes,
        # such as positive or real.
        # Should check for bogus substitutions, such as t for s.

        expr = new
        if isinstance(new, Expr):
            cls = new.__class__
            expr = new.expr
        else:
            cls = self.__class__
            expr = sympify(expr)

        class_map = {(Hs, omegaExpr) : Homega,
                     (Is, omegaExpr) : Iomega,
                     (Vs, omegaExpr) : Vomega,
                     (Ys, omegaExpr) : Yomega,
                     (Zs, omegaExpr) : Zomega,
                     (Hs, fExpr) : Hf,
                     (Is, fExpr) : If,
                     (Vs, fExpr) : Vf,
                     (Ys, fExpr) : Yf,
                     (Zs, fExpr) : Zf,
                     (Hf, omegaExpr) : Homega,
                     (If, omegaExpr) : Iomega,
                     (Vf, omegaExpr) : Vomega,
                     (Yf, omegaExpr) : Yomega,
                     (Zf, omegaExpr) : Zomega,
                     (Homega, fExpr) : Hf,
                     (Iomega, fExpr) : If,
                     (Vomega, fExpr) : Vf,
                     (Yomega, fExpr) : Yf,
                     (Zomega, fExpr) : Zf}

        if (self.__class__, new.__class__) in class_map:
            cls = class_map[(self.__class__, new.__class__)]

        name = canonical_name(old)

        if not isinstance(name, str):
            name = str(name)

        # Replace symbol names with symbol definitions to
        # avoid problems with real or positive attributes.
        if name not in context.symbols:
            raise ValueError('Unknown symbol %s' % old)
        old = context.symbols[name]

        result = self.expr.subs(old, expr)

        # If get empty Piecewise, then result unknowable.
        if result == sym.Piecewise():
            result = sym.nan

        return cls(result)

    def __call__(self, arg):
        """Substitute arg for variable.  If arg is an tuple or list
        return a list.  If arg is an numpy array, return
        numpy array.

        See also evaluate.
        """

        if isinstance(arg, (tuple, list)):
            return [self._subs1(self.var, arg1) for arg1 in arg]

        if isinstance(arg, np.ndarray):
            return np.array([self._subs1(self.var, arg1) for arg1 in arg])

        return self._subs1(self.var, arg)

    def limit(self, var, value, dir='+'):
        """Determine limit of expression(var) at var = value"""

        # Need to use lcapy sympify otherwise could use
        # getattr to call sym.limit.
        ret = sym.limit(self.expr, sympify(var), sympify(value))
        if hasattr(self, 'assumptions'):
            return self.__class__(ret, **self.assumptions)
        return self.__class__(ret)

    def subs(self, *args, **kwargs):
        """Substitute variables in expression, see sympy.subs for usage"""

        if len(args) > 2:
            raise ValueError('Too many arguments')
        if len(args) == 0:
            raise ValueError('No arguments')

        if len(args) == 2:
            return self._subs1(args[0], args[1])

        if  isinstance(args[0], dict):
            dst = self
            for key, val in args[0].items():
                dst = dst._subs1(key, val, **kwargs)

            return dst

        return self._subs1(self.var, args[0])

    @property
    def label(self):

        label = ''
        if hasattr(self, 'quantity'):
            label += self.quantity
            if hasattr(self, 'part'):
                label += ' ' + self.part
        else:
            if hasattr(self, 'part'):
                label += uppercase_name(self.part)
        if hasattr(self, 'units') and self.units != '':
            label += ' (%s)' % self.units
        return label

    @property
    def domain_label(self):

        label = ''
        if hasattr(self, 'domain_name'):
            label += '%s' % self.domain_name
        if hasattr(self, 'domain_units'):
            label += ' (%s)' % self.domain_units
        return label

    def differentiate(self, arg=None):

        if arg is None:
            arg = self.var
        return self.__class__(sym.diff(self.expr, arg))

    def diff(self, arg=None):

        return self.differentiate(arg)

    def debug(self):

        expr = self.expr
        print(expr)
        for symbol in expr.free_symbols:
            print('  %s: %s' % (symbol, symbol.assumptions0))

    def canonical(self):
        return self.__class__(self)


class sfwExpr(Expr):

    def __init__(self, val, **assumptions):

        super(sfwExpr, self).__init__(val, **assumptions)

    def roots(self):
        """Return roots of expression as a dictionary
        Note this may not find them all."""

        return Exprdict(self._ratfun.roots())

    def zeros(self):
        """Return zeroes of expression as a dictionary
        Note this may not find them all."""

        return self.N.roots()

    def poles(self):
        """Return poles of expression as a dictionary
        Note this may not find them all."""

        return self.D.roots()

    def canonical(self):
        """Convert rational function to canonical form with unity
        highest power of denominator.

        See also general, partfrac, mixedfrac, and ZPK"""

        return self.__class__(self._ratfun.canonical(), **self.assumptions)

    def general(self):
        """Convert rational function to general form.

        See also canonical, partfrac, mixedfrac, and ZPK"""

        return self.__class__(self._ratfun.general(), **self.assumptions)

    def partfrac(self):
        """Convert rational function into partial fraction form.

        See also canonical, mixedfrac, general, and ZPK"""

        return self.__class__(self._ratfun.partfrac(), **self.assumptions)

    def mixedfrac(self):
        """Convert rational function into mixed fraction form.

        See also canonical, general, partfrac and ZPK"""

        return self.__class__(self._ratfun.mixedfrac(), **self.assumptions)

    def ZPK(self):
        """Convert to pole-zero-gain (PZK) form.

        See also canonical, general, mixedfrac, and partfrac"""

        return self.__class__(self._ratfun.ZPK(), **self.assumptions)


class sExpr(sfwExpr):
    """s-domain expression or symbol"""

    var = ssym

    def __init__(self, val, **assumptions):

        super(sExpr, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = tExpr

        if self.expr.find(tsym) != set():
            raise ValueError(
                's-domain expression %s cannot depend on t' % self.expr)

    def differentiate(self):
        """Differentiate (multiply by s)"""

        return self.__class__(self.expr * self.var)

    def integrate(self):
        """Integrate (divide by s)"""

        return self.__class__(self.expr / self.var)

    def delay(self, T):
        """Apply delay of T seconds by multiplying by exp(-s T)"""

        T = self.__class__(T)
        return self.__class__(self.expr * sym.exp(-s * T))

    @property
    def jomega(self):
        """Return expression with s = j omega"""

        w = omegaExpr(omegasym)
        return self(sym.I * w)

    def initial_value(self):
        """Determine value at t = 0"""

        return self.__class__(sym.limit(self.expr * self.var, self.var, sym.oo))

    def final_value(self):
        """Determine value at t = oo"""

        return self.__class__(sym.limit(self.expr * self.var, self.var, 0))

    def inverse_laplace(self, **assumptions):
        """Attempt inverse Laplace transform.

        If causal=True the response is zero for t < 0 and
        the result is multiplied by Heaviside(t)
        If ac=True or dc=True the result is extrapolated for t < 0.
        Otherwise the result is only known for t >= 0.

        """

        if assumptions == {}:
            assumptions = self.assumptions

        result = inverse_laplace_transform(self.expr, self.var, tsym, **assumptions)

        if hasattr(self, '_laplace_conjugate_class'):
            result = self._laplace_conjugate_class(result)
        else:
            result = tExpr(result)
        return result

    def time(self, **assumptions):
        return self.inverse_laplace(**assumptions)

    def laplace(self):
        """Convert to s-domain representation"""

        self.infer_assumptions()
        return self.__class__(self, **self.assumptions)

    def fourier(self):
        """Attempt Fourier transform"""

        if self.is_causal:
            return self(j * 2 * pi * f)

        return self.time().fourier()

    def phasor(self, **assumptions):

        return self.time(**assumptions).phasor(**assumptions)

    def transient_response(self, tvector=None):
        """Evaluate transient (impulse) response"""

        texpr = self.inverse_laplace()

        if tvector is None:
            return texpr

        print('Evaluating inverse Laplace transform...')
        return texpr.evaluate(tvector)

    def impulse_response(self, tvector=None):
        """Evaluate transient (impulse) response"""

        return self.transient_response(tvector)

    def step_response(self, tvector=None):
        """Evaluate step response"""

        return (self / self.var).transient_response(tvector)

    def angular_frequency_response(self, wvector=None):
        """Convert to angular frequency domain and evaluate response if
        angular frequency vector specified

        """

        X = self(j * omega)

        if wvector is None:
            return X

        return X.evaluate(wvector)

    def frequency_response(self, fvector=None):
        """Convert to frequency domain and evaluate response if frequency
        vector specified

        """

        X = self(j * 2 * pi * f)

        if fvector is None:
            return X

        return X.evaluate(fvector)

    def response(self, x, t):
        """Evaluate response to input signal x at times t"""

        if len(x) != len(t):
            raise ValueError('x must have same length as t')

        dt = t[1] - t[0]
        if not np.allclose(np.diff(t), np.ones(len(t) - 1) * dt):
            raise (ValueError, 't values not equally spaced')

        N, D, delay = self._as_ratfun_delay()

        Q, M = N.div(D)
        expr = M / D

        N = len(t)

        # Evaluate transient response.
        th = np.arange(N) * dt - dt
        h = sExpr(expr).transient_response(th)

        print('Convolving...')
        ty = t
        y = np.convolve(x, h)[0:N] * dt

        if Q:
            # Handle Dirac deltas and their derivatives.
            C = Q.all_coeffs()
            for n, c in enumerate(C):

                y += c * x

                x = np.diff(x) / dt
                x = np.hstack((x, 0))

        from scipy.interpolate import interp1d

        if delay != 0.0:
            print('Interpolating...')
            # Try linear interpolation; should oversample first...
            y = interp1d(ty, y, bounds_error=False, fill_value=0)
            y = y(t - delay)

        return y

    def decompose(self):

        N, D, delay = self._as_ratfun_delay()

        return N, D, delay

    def evaluate(self, svector=None):

        return super(sExpr, self).evaluate(svector)

    def plot(self, t=None, **kwargs):
        """Plot pole-zero map"""

        from lcapy.plot import plot_pole_zero

        plot_pole_zero(self, **kwargs)


class fExpr(sfwExpr):

    """Fourier domain expression or symbol"""

    var = fsym
    domain_name = 'Frequency'
    domain_units = 'Hz'

    def __init__(self, val, **assumptions):

        assumptions['real'] = True
        super(fExpr, self).__init__(val, **assumptions)
        # Define when class defined.
        self._fourier_conjugate_class = tExpr

        if self.expr.find(ssym) != set():
            raise ValueError(
                'f-domain expression %s cannot depend on s' % self.expr)
        if self.expr.find(tsym) != set():
            raise ValueError(
                'f-domain expression %s cannot depend on t' % self.expr)

    def inverse_fourier(self):
        """Attempt inverse Fourier transform"""

        result = inverse_fourier_transform(self.expr, self.var, tsym)
        if hasattr(self, '_fourier_conjugate_class'):
            result = self._fourier_conjugate_class(result)
        else:
            result = tExpr(result)
        return result

    def plot(self, fvector=None, **kwargs):
        """Plot frequency response at values specified by fvector.

        There are many plotting options, see matplotlib.pyplot.plot.

        For example:
            V.plot(fvector, log_scale=True)
            V.real.plot(fvector, color='black')
            V.phase.plot(fvector, color='black', linestyle='--')

        By default complex data is plotted as separate plots of magnitude (dB)
        and phase.
        """

        from lcapy.plot import plot_frequency
        plot_frequency(self, fvector, **kwargs)


class omegaExpr(sfwExpr):

    """Fourier domain expression or symbol (angular frequency)"""

    var = omegasym
    domain_name = 'Angular frequency'
    domain_units = 'rad/s'

    def __init__(self, val, **assumptions):

        assumptions['real'] = True
        super(omegaExpr, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = tExpr

        if self.expr.find(ssym) != set():
            raise ValueError(
                'omega-domain expression %s cannot depend on s' % self.expr)
        if self.expr.find(tsym) != set():
            raise ValueError(
                'omega-domain expression %s cannot depend on t' % self.expr)

    def inverse_fourier(self):
        """Attempt inverse Fourier transform"""

        return self(2 * pi * f).inverse_fourier()


    def time(self):
        """Alias for inverse_fourier"""

        return self.inverse_fourier()

    def plot(self, wvector=None, **kwargs):
        """Plot angular frequency response at values specified by wvector.

        There are many plotting options, see matplotlib.pyplot.plot.

        For example:
            V.plot(fvector, log_scale=True)
            V.real.plot(fvector, color='black')
            V.phase.plot(fvector, color='black', linestyle='--')

        By default complex data is plotted as separate plots of magnitude (dB)
        and phase.
        """

        from lcapy.plot import plot_angular_frequency
        plot_angular_frequency(self, wvector, **kwargs)


class tExpr(Expr):

    """t-domain expression or symbol"""

    var = tsym
    domain_name = 'Time'
    domain_units = 's'

    def __init__(self, val, **assumptions):

        assumptions['real'] = True
        super(tExpr, self).__init__(val, **assumptions)

        self._fourier_conjugate_class = fExpr
        self._laplace_conjugate_class = sExpr

        if self.expr.find(ssym) != set():
            raise ValueError(
                't-domain expression %s cannot depend on s' % self.expr)

    def infer_assumptions(self):

        self.assumptions['dc'] = False
        self.assumptions['ac'] = False
        self.assumptions['causal'] = False

        var = self.var
        if is_dc(self, var):
            self.assumptions['dc'] = True
            return

        if is_ac(self, var):
            self.assumptions['ac'] = True
            return

        if is_causal(self, var):
            self.assumptions['causal'] = True

    def laplace(self):
        """Determine one-side Laplace transform with 0- as the lower limit."""

        # The assumptions are required to help with the inverse Laplace
        # tranform is reequired.
        self.infer_assumptions()
        result = laplace_transform(self.expr, self.var, ssym)

        if hasattr(self, '_laplace_conjugate_class'):
            result = self._laplace_conjugate_class(result, **self.assumptions)
        else:
            result = sExpr(result, **self.assumptions)
        return result

    def fourier(self):
        """Attempt Fourier transform"""

        result = fourier_transform(self.expr, self.var, fsym)

        if hasattr(self, '_fourier_conjugate_class'):
            result = self._fourier_conjugate_class(result, **self.assumptions)
        else:
            result = fExpr(result **self.assumptions)
        return result

    def phasor(self, **assumptions):

        check = ACChecker(self, t)
        if not check.is_ac:
            raise ValueError('Do not know how to convert %s to phasor' % self)
        phasor = Phasor(check.amp * exp(j * check.phase), omega=check.omega)
        return phasor

    def plot(self, t=None, **kwargs):

        from lcapy.plot import plot_time
        plot_time(self, t, **kwargs)


class cExpr(Expr):

    """Constant real expression or symbol.

    If symbols in the expression are known to be negative, use
    cExpr(expr, positive=False)

    """

    def __init__(self, val, **assumptions):

        symbols = symbols_find(val)
        for symbol in ('s', 'omega', 't', 'f'):
            if symbol in symbols:
                raise ValueError(
                    'constant expression %s cannot depend on %s' % (val, symbol))

        assumptions['real'] = True
        if 'positive' not in assumptions:
            assumptions['positive'] = True
        super(cExpr, self).__init__(val, **assumptions)

    def rms(self):
        return {Vconst: Vt, Iconst : It}[self.__class__](self)


class Phasor(Expr):

    # Could convert Vphasor + Vconst -> VSuper but that is not really
    # the scope for types such as Vphasor and Vconst.

    def __init__(self, val, **assumptions):

        assumptions['positive'] = True
        super (Phasor, self).__init__(val, **assumptions)

    def __compat_add__(self, x, op):

        cls = self.__class__
        xcls = x.__class__

        # Special case for zero.
        if isinstance(x, int) and x == 0:
            return cls, self, cls(x), self.assumptions

        if not isinstance(x, Phasor):
            raise TypeError('Incompatible arguments %s and %s for %s' %
                            (repr(self), repr(x), op))

        if self.omega != x.omega:
            raise ValueError('Cannot combine %s(%s, omega=%s)'
                             ' with %s(%s, omega=%s)' %
                             (cls.__name__, self, self.omega,
                              xcls.__name__, x, x.omega))
        return cls, self, x, {}

    def __compat_mul__(self, x, op):

        cls = self.__class__
        xcls = x.__class__

        # Perhaps check explicitly for int, float?
        if not isinstance(x, Expr):
            return cls, self, cls(x), self.assumptions

        if isinstance(x, omegaExpr):
            return cls, self, x, self.assumptions

        if not isinstance(x, Phasor):
            raise TypeError('Incompatible arguments %s and %s for %s' %
                            (repr(self), repr(x), op))

        if self.omega != x.omega:
            raise ValueError('Cannot combine %s(%s, omega=%s)'
                             ' with %s(%s, omega=%s)' %
                             (cls.__name__, self, self.omega,
                              xcls.__name__, x, x.omega))
        return cls, self, x, self.assumptions

    def time(self, **assumptions):
        """Convert to time domain representation"""

        omega = self.omega
        if hasattr(omega, 'expr'):
            # TODO: Fix inconsistency.  Sometimes omega is a symbol.
            omega = omega.expr
            
        if self.is_complex:
            result = self.expr * exp(j * omega * t)
        else:
            result = self.real.expr * cos(omega * t) + self.imag.expr * sin(omega * t)

        if hasattr(self, '_laplace_conjugate_class'):
            return self._laplace_conjugate_class(result)
        return tExpr(result)

    def fourier(self):
        """Attempt Fourier transform"""

        # TODO: Could optimise this...
        return self.time().fourier()

    def laplace(self):
        """Convert to Laplace domain representation"""

        return self.time().laplace()

    def phasor(self):
        """Convert to phasor representation"""
        return self.__class__(self, **self.assumptions)

    def rms(self):
        return {Vphasor: Vt, Iphasor : It}[self.__class__](0.5 * self)

    def plot(self, fvector=None, **kwargs):

        if self.omega != omegasym:
            self.fourier.plot(fvector, **kwargs)
        omegaExpr(self).plot(fvector, **kwargs)


class Vphasor(Phasor):

    def __init__(self, val, **assumptions):

        super(Vphasor, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Vt

    def cpt(self):

        v = self
        if v.is_number or self.is_ac:
            return Vac(v)

        return V(self)


class Iphasor(Phasor):

    def __init__(self, val, **assumptions):

        super(Iphasor, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = It

    def cpt(self):

        i = self
        if i.is_number or self.is_ac:
            return Iac(i)

        return I(self)


class Vconst(cExpr):

    def __init__(self, val, **assumptions):

        super(Vconst, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Vt

    def cpt(self):
        return Vdc(self)

    def time(self):
        return Vt(self)


class Iconst(cExpr):

    def __init__(self, val, **assumptions):

        super(Iconst, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = It

    def cpt(self):
        return Idc(self)

    def time(self):
        return It(self)


s = sExpr('s')
t = tExpr('t')
f = fExpr('f')
omega = omegaExpr('omega')
pi = sym.pi
j = sym.I
oo = sym.oo
inf = sym.oo


def pprint(expr):

    # If interactive use pretty, otherwise use latex
    if hasattr(sys, 'ps1'):
        print(pretty(expr))
    else:
        print(latex_str(latex(expr)))

        
class Matrix(sym.Matrix):

    # Unlike numpy.ndarray, the sympy.Matrix runs all the elements
    # through sympify, creating sympy objects and thus losing the
    # original type information and associated methods.  As a hack, we
    # try to wrap elements when they are read using __getitem__.  This
    # assumes that all the elements have the same type.  This is not
    # the case for A, B, G, and H matrices.  This could he handled by
    # having another matrix to specify the type for each element.

    _typewrap = sExpr

    def __getitem__(self, key):

        item = super(Matrix, self).__getitem__(key)

        # The following line is to handle slicing used
        # by latex method.
        if isinstance(item, sym.Matrix):
            return item

        if hasattr(self, '_typewrap'):
            return self._typewrap(item)

        return item

    def pprint(self):

        return pprint(self)

    def latex(self):

        return latex(self)

    def _reformat(self, method):
        """Helper method for reformatting expression"""

        new = copy(self)

        for i in range(self.rows):
            for j in range(self.cols):
                new[i, j] = getattr(self[i, j], method)()

        return new

    def canonical(self):

        return self._reformat('canonical')

    def general(self):

        return self._reformat('general')

    def mixedfrac(self):

        return self._reformat('mixedfrac')

    def partfrac(self):

        return self._reformat('partfrac')

    def ZPK(self):

        return self._reformat('ZPK')

    # TODO. There is probably a cunning way to automatically handle
    # the following.

    def inv(self):

        return self.__class__(sym.Matrix(self).inv())

    def det(self):

        return sym.Matrix(self).det()


class Vector(Matrix):

    def __new__(cls, *args):

        args = [sympify(arg) for arg in args]

        if len(args) == 2:
            return super(Vector, cls).__new__(cls, (args[0], args[1]))

        return super(Vector, cls).__new__(cls, *args)


def DeltaWye(Z1, Z2, Z3):

    ZZ = (Z1 * Z2 + Z2 * Z3 + Z3 * Z1)
    return (ZZ / Z1, ZZ / Z2, ZZ / Z3)


def WyeDelta(Z1, Z2, Z3):

    ZZ = Z1 + Z2 + Z3
    return (Z2 * Z3 / ZZ, Z1 * Z3 / ZZ, Z1 * Z2 / ZZ)


def tf(numer, denom=1, var=None):
    """Create a transfer function from lists of the coefficient
    for the numerator and denominator"""

    if var is None:
        var = ssym

    N = sym.Poly(numer, var)
    D = sym.Poly(denom, var)

    return Hs(N / D)


def zp2tf(zeros, poles, K=1, var=None):
    """Create a transfer function from lists of zeros and poles,
    and from a constant gain"""

    if var is None:
        var = ssym
    return Hs(_zp2tf(zeros, poles, K, var))


# Perhaps use a factory to create the following classes?

class Zs(sExpr):

    """s-domain impedance value"""

    quantity = 'Impedance'
    units = 'ohms'

    def __init__(self, val, **assumptions):

        super(Zs, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Zt

    @classmethod
    def C(cls, Cval):

        return cls(1 / (s * Cval))

    @classmethod
    def G(cls, Gval):

        return cls(1 / Gval)

    @classmethod
    def L(cls, Lval):

        return cls(s * Lval)

    @classmethod
    def R(cls, Rval):

        return cls(Rval)

    def cpt(self):

        if self.is_number or self.is_dc:
            return R(self.expr)

        z = self * s

        if z.is_number:
            return C((1 / z).expr)

        z = self / s

        if z.is_number:
            return L(z.expr)

        return Z(self)


class Ys(sExpr):

    """s-domain admittance value"""

    quantity = 'Admittance'
    units = 'siemens'

    def __init__(self, val, **assumptions):

        super(Ys, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Yt

    @classmethod
    def C(cls, Cval):

        return cls(s * Cval)

    @classmethod
    def G(cls, Gval):

        return cls(Gval)

    @classmethod
    def L(cls, Lval):

        return cls(1 / (s * Lval))

    @classmethod
    def R(cls, Rval):

        return cls(1 / Rval)

    def cpt(self):

        if self.is_number or self.is_dc:
            return G(self.expr)

        y = self * s

        if y.is_number:
            return L((1 / y).expr)

        y = self / s

        if y.is_number:
            return C(y.expr)

        return Y(self)


class Vs(sExpr):

    """s-domain voltage (units V s / radian)"""

    quantity = 's-Voltage'
    units = 'V/Hz'

    def __init__(self, val, **assumptions):

        super(Vs, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Vt

    def cpt(self):
        return V(self)


class Is(sExpr):

    """s-domain current (units A s / radian)"""

    quantity = 's-Current'
    units = 'A/Hz'

    def __init__(self, val, **assumptions):

        super(Is, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = It

    def cpt(self):
        return I(self)


class Hs(sExpr):

    """s-domain ratio"""

    quantity = 's-ratio'
    units = ''

    def __init__(self, val, **assumptions):

        super(Hs, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Ht


class Yt(tExpr):

    """t-domain 'admittance' value"""

    units = 'siemens/s'

    def __init__(self, val, **assumptions):

        super(Yt, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Ys
        self._fourier_conjugate_class = Yf


class Zt(tExpr):

    """t-domain 'impedance' value"""

    units = 'ohms/s'

    def __init__(self, val, **assumptions):

        super(Zt, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Zs
        self._fourier_conjugate_class = Zf


class Vt(tExpr):

    """t-domain voltage (units V)"""

    quantity = 'Voltage'
    units = 'V'

    def __init__(self, val, **assumptions):

        super(Vt, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Vs
        self._fourier_conjugate_class = Vf


class It(tExpr):

    """t-domain current (units A)"""

    quantity = 'Current'
    units = 'A'

    def __init__(self, val, **assumptions):

        super(It, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Is
        self._fourier_conjugate_class = If


class Ht(tExpr):

    """impulse response"""

    quantity = 'Impulse response'
    units = '1/s'

    def __init__(self, val, **assumptions):

        super(Ht, self).__init__(val, **assumptions)
        self._laplace_conjugate_class = Hs
        self._fourier_conjugate_class = Hf


class Yf(fExpr):

    """f-domain admittance"""

    quantity = 'Admittance'
    units = 'siemens'

    def __init__(self, val, **assumptions):

        super(Yf, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Yt


class Zf(fExpr):

    """f-domain impedance"""

    quantity = 'Impedance'
    units = 'ohms'

    def __init__(self, val, **assumptions):

        super(Zf, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Zt


class Hf(fExpr):

    """f-domain transfer function response"""

    quantity = 'Transfer function'
    units = ''

    def __init__(self, val, **assumptions):

        super(Hf, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Ht


class Vf(fExpr):

    """f-domain voltage (units V/Hz)"""

    quantity = 'Voltage spectrum'
    units = 'V/Hz'

    def __init__(self, val, **assumptions):

        super(Vf, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Vt


class If(fExpr):

    """f-domain current (units A/Hz)"""

    quantity = 'Current spectrum'
    units = 'A/Hz'

    def __init__(self, val, **assumptions):

        super(If, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = It


class noiseExpr(omegaExpr):
    """Frequency domain (one-sided) noise spectrum expression.  When
    performing arithmetic on two noiseExpr expressions it is assumed
    that they are correlated, so 3 + 4 = 7 and not 5 if added on a
    power basis.

    The Super class handles uncorrelated noise.

    """
    one_sided = True

    def rms(self):
        """Calculate rms value."""

        P = sym.integrate(self.expr**2, (self.var, 0, sym.oo)) / (2 * sym.pi)
        rms = sym.sqrt(P)
        # TODO: Use rms class?
        return self._fourier_conjugate_class(rms)

    def time(self):
        print('Warning: no time representation for noise expression'
              ', assumed zero: use rms()')
        return 0

    def autocorrelation(self):
        # Convert to two-sided spectrum
        S = self.subs(self.var, abs(self.var)) / sqrt(2)
        return S.inverse_fourier()


class Vn(noiseExpr):

    """f-domain noise voltage (units V/rtHz)"""

    quantity = 'Voltage noise spectrum'
    units = 'V/rtHz'

    def __init__(self, val, **assumptions):

        assumptions['positive'] = True
        super(Vn, self).__init__(val, **assumptions)
        # FIXME
        self._fourier_conjugate_class = Vt


class In(noiseExpr):

    """f-domain noise current (units A/rtHz)"""

    quantity = 'Current noise spectrum'
    units = 'A/rtHz'

    def __init__(self, val, **assumptions):

        assumptions['positive'] = True
        super(In, self).__init__(val, **assumptions)
        # FIXME
        self._fourier_conjugate_class = It


class Yomega(omegaExpr):

    """omega-domain admittance"""

    quantity = 'Admittance'
    units = 'siemens'

    def __init__(self, val, **assumptions):

        super(Yomega, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Yt

    def cpt(self):

        if self.is_number:
            return G(self.expr)

        y = self * sym.I * omega

        if y.is_number:
            return L((1 / y).expr)

        y = self / (sym.I * omega)

        if y.is_number:
            return C(y.expr)

        return Y(self)


class Zomega(omegaExpr):

    """omega-domain impedance"""

    quantity = 'Impedance'
    units = 'ohms'

    def __init__(self, val, **assumptions):

        super(Zomega, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Zt

    def cpt(self):

        if self.is_number:
            return R(self.expr)

        z = self * sym.I * omega

        if z.is_number:
            return C((1 / z).expr)

        z = self / (sym.I * omega)

        if z.is_number:
            return L(z.expr)

        return Z(self)


class Vomega(omegaExpr):

    """omega-domain voltage (units V/rad/s)"""

    quantity = 'Voltage spectrum'
    units = 'V/rad/s'

    def __init__(self, val, **assumptions):

        super(Vomega, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Vt


class Iomega(omegaExpr):

    """omega-domain current (units A/rad/s)"""

    quantity = 'Current spectrum'
    units = 'A/rad/s'

    def __init__(self, val, **assumptions):

        super(Iomega, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = It


class Homega(omegaExpr):

    """omega-domain transfer function response"""

    quantity = 'Transfer function'
    units = ''

    def __init__(self, val, **assumptions):

        super(Homega, self).__init__(val, **assumptions)
        self._fourier_conjugate_class = Ht


class VsVector(Vector):

    _typewrap = Vs


class IsVector(Vector):

    _typewrap = Is


class YsVector(Vector):

    _typewrap = Ys


class ZsVector(Vector):

    _typewrap = Zs


def _funcwrap(func, *args):

    cls = args[0].__class__

    tweak_args = list(args)
    for m, arg in enumerate(args):
        if isinstance(arg, Expr):
            tweak_args[m] = arg.expr

    result = func(*tweak_args)

    if hasattr(args[0], 'expr'):
        result = cls(result)

    return result


def sin(expr):

    return _funcwrap(sym.sin, expr)


def cos(expr):

    return _funcwrap(sym.cos, expr)


def tan(expr):

    return _funcwrap(sym.tan, expr)


def atan(expr):

    return _funcwrap(sym.atan, expr)


def atan2(expr1, expr2):

    return _funcwrap(sym.atan2, expr1, expr2)


def gcd(expr1, expr2):

    return _funcwrap(sym.gcd, expr1, expr2)


def exp(expr):

    return _funcwrap(sym.exp, expr)


def sqrt(expr):

    return _funcwrap(sym.sqrt, expr)


def log(expr):

    return _funcwrap(sym.log, expr)


def log10(expr):

    return _funcwrap(sym.log, expr, 10)


def Heaviside(expr):
    """Heaviside's unit step"""

    return _funcwrap(sym.Heaviside, expr)


def H(expr):
    """Heaviside's unit step"""

    return Heaviside(expr)


def u(expr):
    """Heaviside's unit step"""

    return Heaviside(expr)


def DiracDelta(*args):
    """Dirac delta (impulse)"""

    return _funcwrap(sym.DiracDelta, *args)


def delta(expr, *args):
    """Dirac delta (impulse)"""

    return DiracDelta(expr, *args)


class Super(Exprdict):

    def __init__(self, *args):
        super (Super, self).__init__()
        for arg in args:
            self.add(arg)

    def _repr_pretty_(self, p, cycle):
        if self == {}:
            p.text(pretty(0))
        else:
            p.text(pretty(self))

    def __getitem__(self, key):
        # This allows a[omega] to work if omega used as key
        # instead of 'omega'.
        if hasattr(key, 'expr'):
            key = key.expr
        return super(Super, self).__getitem__(key)

    def ac_keys(self):
        """Return list of keys for all ac components"""

        keys = self.keys()
        for key in ('dc', 's', 'n'):
            if key in keys:
                keys.remove(key)
        return keys

    @property
    def has_dc(self):
        return 'dc' in self

    @property
    def has_ac(self):
        return self.ac_keys() != []

    @property
    def has_s(self):
        return 's' in self

    @property
    def has_n(self):
        return 'n' in self

    @property
    def is_dc(self):
        return self.keys() == ['dc']

    @property
    def is_ac(self):
        return self.ac_keys() == self.keys()

    @property
    def is_s(self):
        return self.keys() == ['s']

    @property
    def is_n(self):
        return self.keys() == ['n']

    @property
    def is_causal(self):
        return self.is_s and self.s.is_causal

    @property
    def is_superposition(self):
        return len(self.keys()) > 1

    def __add__(self, x):
        new = copy(self)
        if isinstance(x, Super):
            for value in x.values():
                new.add(value)
        else:
            new.add(x)
        return new

    def __radd__(self, x):
        return self.__add__(x)

    def __sub__(self, x):
        return -x + self

    def __rsub__(self, x):
        return -self + x

    def __neg__(self):
        new = self.__class__()
        for kind, value in self.items():
            if kind != 'n':
                value = -value
            new[kind] = value
        return new

    def __scale__(self, x):
        new = self.__class__()
        for kind, value in self.items():
            # TODO: Perhaps should ensure 'n' field positive?
            new[kind] = value * x
        return new

    # TODO, this kills Ipython
    # def __eq__(self, x):
    #     diff = self - x
    #     for kind, value in diff.items():
    #         if value != 0:
    #             return False
    #     return True

    def select(self, kind):
        if kind not in self:
            if kind not in self.transform_domains:
                kind = 'ac'
            return self.transform_domains[kind](0)
        return self[kind]

    def _kind(self, value):
        if isinstance(value, Phasor):
            # Use angular frequency for key.  This can be a nuisance
            # for numerical values since cannot use x.3 syntax
            # say for an angular frequency of 3.
            key = value.omega
            if hasattr(key, 'expr'):
                key = key.expr
            return key

        for kind, mtype in self.transform_domains.items():
            if isinstance(value, mtype):
                return kind
        return None

    def _decompose(self, value):

        dc = value.expr.coeff(tsym, 0)
        if dc != 0:
            self.add(cExpr(dc))
            value -= dc

        if value == 0:
            return

        ac = 0
        terms = value.expr.as_ordered_terms()
        for term in terms:
            if is_ac(term, tsym):
                self.add(tExpr(term).phasor())
                ac += term

        value -= ac
        if value == 0:
            return

        sval = value.laplace()
        return self.add(sval)

    def _parse(self, string):
        """Parse t or s-domain expression or symbol, interpreted in time
        domain if not containing s, omega, or f.  Return most
        appropriate transform domain.

        """

        symbols = symbols_find(string)

        if 's' in symbols:
            return self.add(sExpr(string))

        if 'omega' in symbols:
            if 't' in symbols:
                # Handle cos(omega * t)
                return self.add(tExpr(string))
            return self.add(omegaExpr(string))

        if 'f' in symbols:
            # TODO, handle AC of different frequency
            return self.add(fExpr(string))

        return self._decompose(tExpr(string))

    def add(self, value):
        if value == 0:
            return

        if isinstance(value, Super):
            for kind, value in value.items():
                self.add(value)
            return

        if isinstance(value, six.string_types):
            return self._parse(value)

        if isinstance(value, (int, float)):
            return self.add(self.transform_domains['dc'](value))

        if isinstance(value, tExpr):
            return self._decompose(value)

        kind = self._kind(value)
        if kind is None:
            if value.__class__ in self.type_map:
                value = self.type_map[value.__class__](value)
            else:
                for cls1, cls2 in self.type_map.items():
                    if isinstance(value, cls1):
                        value = cls2(value)
                        break
            kind = self._kind(value)

        if kind is None:
            raise ValueError('Cannot handle value %s of type %s' %
                             (value, type(value).__name__))

        if kind == 'n':
            valuesq = (value * value.conjugate).simplify()
            if kind not in self:
                self[kind] = sqrt(valuesq)
            else:
                # Assume noise uncorrelated.
                value1sq = (self[kind] * self[kind].conjugate).simplify()
                self[kind] = sqrt((value1sq + valuesq).simplify())
        else:
            if kind not in self:
                self[kind] = value
            else:
                self[kind] += value

    @property
    def dc(self):
        return self.select('dc')

    @property
    def ac(self):
        return Exprdict({k: v for k, v in self.items() if k in self.ac_keys()})

    @property
    def s(self):
        return self.select('s')

    @property
    def n(self):
        return self.select('n')

    def time(self):

        result = self.time_class(0)

        # TODO, integrate noise
        for val in self.values():
            if hasattr(val, 'time'):
                result += val.time()
            else:
                result += val
        return result

    def laplace(self):
        # TODO, could optimise
        return self.time().laplace()

    def fourier(self):
        # TODO, could optimise
        return self.time().fourier()

    @property
    def t(self):
        return self.time()

    def canonical(self):
        new = self.__class__()
        for kind, value in self.items():
            new[kind] = value.canonical()

        return new

    def simplify(self):
        new = self.__class__()
        for kind, value in self.items():
            new[kind] = value.simplify()

        return new


class Vsuper(Super):

    type_map = {cExpr: Vconst, sExpr : Vs, noiseExpr: Vn, omegaExpr: Vphasor}
    transform_domains = {'s': Vs, 'ac' : Vphasor, 'dc' : Vconst, 'n' : Vn}
    time_class = Vt

    def __mul__(self, x):
        if isinstance(x, (int, float)):
            return self.__scale__(x)

        if not isinstance(x, Ys):
            raise TypeError("Unsupported types for *: 'Vsuper' and '%s'" %
                            type(x).__name__)
        new = Isuper()
        if 'dc' in self:
            # TODO, fix types
            new += Iconst(self['dc'] * cExpr(x.jomega(0)))
        for key in self.ac_keys():
            new += self[key] * x.jomega(self[key].omega)
        if 'n' in self:
            new += self['n'] * x.jomega
        if 's' in self:
            new += self['s'] * x
        return new

    def __div__(self, x):
        if isinstance(x, (int, float)):
            return self.__scale__(1 / x)

        if not isinstance(x, Zs):
            raise TypeError("Unsupported types for /: 'Vsuper' and '%s'" %
                            type(x).__name__)
        return self * Ys(1 / x)

    def cpt(self):
        return V(self.time())

class Isuper(Super):

    type_map = {cExpr: Iconst, sExpr : Is, noiseExpr: In, omegaExpr: Iphasor}
    transform_domains = {'s': Is, 'ac' : Iphasor, 'dc' : Iconst, 'n' : In}
    time_class = It

    def __mul__(self, x):
        if isinstance(x, (int, float)):
            return self.__scale__(x)

        if not isinstance(x, Zs):
            raise TypeError("Unsupported types for *: 'Isuper' and '%s'" %
                            type(x).__name__)
        new = Vsuper()
        if 'dc' in self:
            # TODO, fix types
            new += Vconst(self['dc'] * cExpr(x.jomega(0)))
        for key in self.ac_keys():
            new += self[key] * x.jomega(self[key].omega)
        if 'n' in self:
            new += self['n'] * x.jomega
        if 's' in self:
            new += self['s'] * x
        return new

    def __div__(self, x):
        if isinstance(x, (int, float)):
            return self.__scale__(1 / x)

        if not isinstance(x, Ys):
            raise TypeError("Unsupported types for /: 'Isuper' and '%s'" %
                            type(x).__name__)
        return self * Zs(1 / x)

    def cpt(self):
        return I(self.time())
    
    
def vtype_select(kind):
    try:
        return {'s' : Vs, 'n' : Vn, 'ac' : Vphasor, 'dc' : Vconst}[kind]
    except KeyError:
        return Vphasor


def itype_select(kind):
    try:
        return {'s' : Vs, 'n' : Vn, 'ac' : Vphasor, 'dc' : Vconst}[kind]
    except KeyError:
        return Iphasor

from lcapy.oneport import L, C, R, G, Idc, Vdc, Iac, Vac, I, V, Z, Y
