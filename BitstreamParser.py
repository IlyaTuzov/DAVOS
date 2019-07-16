from Davos_Generic import *
from collections import OrderedDict


def get_lut_to_bel_map(cellType, BelEquation):
    inputnum = int(re.findall('LUT([0-9]+)', cellType)[0])
    for i in range(10): BelEquation = BelEquation.replace('A{0:d}+~A{0:d}'.format(i),'')
    for term in BelEquation.split('+'):
        vardict = OrderedDict.fromkeys(re.findall('(A[0-9]+)', term))
        if len(vardict) == inputnum:
            return( OrderedDict(zip(['I{0:d}'.format(i) for i in range(inputnum)], vardict.keys())) )





#Bitstream mapping for complete 6-input LUT
vars = ['A1', 'A2', 'A3', 'A4', 'A5', 'A6']
T = Table('LUT', vars)
for i in range(2**len(vars)):
    r = [(i>>j)&0x1 for j in range(len(vars))]
    T.add_row(r)
T.add_column('Bit', [63,47,62,46,61,45,60,44,15,31,14,30,13,29,12,28,59,43,58,42,57,41,56,40,11,27,10,26, 9,25, 8,24,55,39,54,38,53,37,52,36, 7,23, 6,22, 5,21, 4,20,51,35,50,34,49,33,48,32, 3,19, 2,18, 1,17, 0,16])


#eq = 'O6=(A6+~A6)*((A4*A1*A2*A3*(~A5))+(A4*A1*A2*(~A3))+(A4*A1*(~A2))+(A4*(~A1))+((~A4)*A1)+((~A4)*(~A1)*A2)+((~A4)*(~A1)*(~A2)*A3)+((~A4)*(~A1)*(~A2)*(~A3)*A5))'
eq = 'A6*A5*A4*A3*A2*A1'
connections = get_lut_to_bel_map('LUT.others.LUT6', eq)
print connections.values()

#filter-out unused inputs (and LUT rows)
for v in vars:
    if not v in connections.values() + ['Bit']:
        T.filter(v, 1)

res = []
#reorder columns according to connections of logical LUT
T.reorder_columns(connections.values() + ['Bit'])
for i in range(2**len(connections)):
    r = [(i>>j)&0x1 for j in range(len(connections))]
    index, val = T.search_row(r,0)
    res.append(val[-1])

print res


with open('C:\Projects\Log1.csv', 'w') as f:
    f.write(T.to_csv())



