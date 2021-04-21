from ..helper.datatable import ColummDataType


def datatable(self):
    cols = [['', ColummDataType.STRING], ['Value', ColummDataType.FLOAT]]
    cols[0].append('Sharpe-Ratio')

    a = self.get_analysis()
    if len(a):
        cols[1].append(a['sharperatio'])
    else:
        cols[1].append('')
    return 'Sharpe-Ratio', [cols]
