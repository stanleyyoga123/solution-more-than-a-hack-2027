import {chart, inspect, states} from './diagnostic_charts.js';

export function renderECDF(container, groups, output) {
  const {svg,add}=chart(container,'How often a player is within each distance of the ball',300);
  svg.setAttribute('style', 'width: 640px');
  const maximum=Math.max(1,...Object.values(groups).flatMap(group=>group.ecdf.map(point=>point.metres)));
  for(let i=0;i<=4;i++) {
    const x=70+i*130,y=240-i*50;
    add('line',{x1:70,x2:590,y1:y,y2:y,class:'chart-grid'});
    add('text',{x:58,y:y+4,'text-anchor':'end',class:'chart-tick'},`${i*25}%`);
    add('text',{x,y:262,'text-anchor':'middle',class:'chart-tick'},(maximum*i/4).toFixed(1));
  }
  add('text',{x:70,y:20,class:'chart-axis'},'Frames within this distance (%)');
  add('text',{x:330,y:292,'text-anchor':'middle',class:'chart-axis'},'Distance from ball to nearest player (m)');
  const marks=[], descriptions=[];
  for(const [state,group] of Object.entries(groups)) {
    let path='M 70 240';
    group.ecdf.forEach(point=>{path+=` H ${70+520*point.metres/maximum} V ${240-200*point.fraction}`;});
    if(group.ecdf.length) {
      path+=' H 590';
      marks.push(add('path',{d:path,fill:'none',stroke:states[state][1],'stroke-width':2,style:`stroke: ${states[state][1]}`}));
      descriptions.push(`${states[state][0]} · ${group.samples.toLocaleString()} measured frames · middle distance ${group.median_metres.toFixed(2)} m`);
    }
  }
  inspect(svg,marks,descriptions,output);
}

export function renderBars(container, rows, output, axis='Frames') {
  const height=rows.length*34+65;
  const {svg,add}=chart(container,axis,height,760);
  svg.style.width='760px';
  const maximum=Math.max(1,...rows.map(row=>row.value));
  const marks=rows.map((row,index)=>{
    const y=20+index*34;
    add('text',{x:280,y:y+14,'text-anchor':'end',class:'chart-label'},row.label);
    add('text',{x:745,y:y+14,'text-anchor':'end',class:'chart-value'},row.value.toLocaleString());
    return add('rect',{x:295,y,width:390*row.value/maximum,height:18,fill:row.color || 'var(--accent)'});
  });
  add('text',{x:490,y:height-8,'text-anchor':'middle',class:'chart-axis'},axis);
  inspect(svg,marks,rows.map(row=>`${row.label}: ${row.value.toLocaleString()} ${axis.toLowerCase()}`),output);
}
