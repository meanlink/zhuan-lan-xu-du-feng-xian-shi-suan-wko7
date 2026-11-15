export function parseCSV(text){
 const rows=[];let row=[],cell='',quote=false;
 for(let i=0;i<text.length;i++){const c=text[i];if(c==='"'){if(quote&&text[i+1]==='"'){cell+='"';i++;}else quote=!quote;}else if(c===','&&!quote){row.push(cell);cell='';}else if((c==='\n'||c==='\r')&&!quote){if(c==='\r'&&text[i+1]==='\n')i++;row.push(cell);if(row.some(Boolean))rows.push(row);row=[];cell='';}else cell+=c;}
 if(quote)throw new Error('CSV 引号未闭合');row.push(cell);if(row.some(Boolean))rows.push(row);
 const keys=rows.shift()?.map(k=>k.replace(/^\uFEFF/,'').trim());if(!keys?.length)throw new Error('CSV 为空');
 return rows.map((r,i)=>{if(r.length!==keys.length)throw new Error('CSV 第 '+(i+2)+' 行列数不一致');return Object.fromEntries(keys.map((k,j)=>[k,r[j]]));});
}
