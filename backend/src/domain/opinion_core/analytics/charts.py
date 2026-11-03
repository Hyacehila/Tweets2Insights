"""Deterministic distribution heatmaps with their complete numerical source tables."""
import html


def build_charts(observations):
    results={}
    for field in ('sentiment','stance'):
        windows=observations['windows']
        width,height=900,max(120,30+len(windows)*22)
        n=len(observations['bins'])-1
        cells=[]; table=[]
        for row,w in enumerate(windows):
            data=w['fields'][field]
            values=data['mass']
            table.append({'start':w['start'],'raw_n':w['raw_n'],'valid_n':data['valid_n'],
                          'coverage':data['coverage'],'mass':values})
            cells.append(f'<text x="0" y="{row*22+45}" font-size="11">{html.escape(w["start"][:16])}</text>')
            for column in range(n):
                value=values[column] if values is not None else None
                shade=255-int(200*value) if value is not None else 215
                color=f'rgb({shade},{shade},255)' if value is not None else '#ddd'
                cells.append(f'<rect x="{150+column*700/n}" y="{30+row*22}" width="{700/n}" height="20" fill="{color}"/>')
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><rect width="100%" height="100%" fill="white"/><text x="150" y="17">{field}: -1 to +1; grey = missing</text>'+''.join(cells)+'</svg>'
        results[field]={'svg':svg,'data':table,'bins':observations['bins'],'schema_version':observations['schema_version']}
    return results
