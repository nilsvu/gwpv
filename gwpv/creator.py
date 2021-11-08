import numpy as np
import h5py

D = 10
num_points = 10
X = np.linspace(-D, D, num_points)
Y = X
Z = X
x, y, z = map(lambda arr: arr.flatten(order='F'), np.meshgrid(X, Y, Z, indexing='ij'))
r = np.sqrt(x ** 2 + y ** 2 + z ** 2)
th = np.arccos(z / r)
phi = np.arctan2(y, x)
t = np.linspace(-102, 1000, 100)
data_grid = np.zeros((len(t)+1,len(th)+1), dtype=np.complex_)
data_grid[1:,0] = t

#for i in range(len(th)):
#    data_grid[0, i + 1] = str(round(th[i],3))+"_"+str(round(th[i],3))
for i in range(len(th)):
    data_grid[0, i+1] = th[i] + 1j*phi[i]
for i in range(len(t)):
    data_grid[i + 1, 1:] = (1 - 1j)*(np.cos(th)*1/(t[i]+101) + np.sin(th)*1/((t[i]+50)**2)*np.cos(0.1*phi))

h5f = h5py.File('analytics.h5', 'w')
grp = h5f.create_group('Extrapolated_N2.dir')
grp.create_dataset('analytics', data=data_grid)



th1 = np.linspace(0, np.pi, 10)
phi1 = np.linspace(0, 2*np.pi, 20)

Th, Phi = map(lambda arr: arr.flatten(order='F'), np.meshgrid(th1, phi1, indexing='ij'))
data_grid1 = np.zeros((len(t)+1,len(Th)+1), dtype=np.complex_)
data_grid1[1:,0] = t
for i in range(len(Th)):
    data_grid1[0, i+1] = Th[i] + 1j*Phi[i]
for i in range(len(t)):
    data_grid1[i + 1, 1:] = (1 - 1j)*(np.cos(Th)*1/(t[i]+101) + np.sin(Th)*1/((t[i]+50)**2)*np.cos(0.1*Phi))

h5f = h5py.File('analytics1.h5', 'w')
grp1 = h5f.create_group('Extrapolated_N2.dir')
grp1.create_dataset('analytics1', data=data_grid1)