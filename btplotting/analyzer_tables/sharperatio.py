from ..helper.datatable import ColummDataType


def datatable(self):
    cols = [['', ColummDataType.STRING], ['Value', ColummDataType.FLOAT]]
    cols[0].append('Sharpe-Ratio')

    a = self.get_analysis()
    cols[1].append(a['sharperatio'])
    return "Sharpe-Ratio", [cols]
