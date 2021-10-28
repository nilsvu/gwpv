import numpy as np

def genarate_analytic(D,N):

    X = np.linspace(-D, D, N)
    Y = X
    Z = X
    x, y, z = map(lambda arr: arr.flatten(order='F'), np.meshgrid(X, Y, Z, indexing='ij'))
    r = np.sqrt(x ** 2 + y ** 2 + z ** 2)
    th = np.arccos(z / r)
    phi = np.arctan2(y, x)
    return np.cos(phi)*np.sin(th) + 1j * np.cos(th)*np.sin(phi)
