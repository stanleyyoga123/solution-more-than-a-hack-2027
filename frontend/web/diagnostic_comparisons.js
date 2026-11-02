import {eventName} from './diagnostic_copy.js';
import {states} from './diagnostic_charts.js';
/** Compact, accessible comparisons with explicit denominators and shared scales. */
import {fractionAt, rateText, stateName, eventRows} from './diagnostic_analysis.js';

export function matrix(parent, node, caption, headings, rows) {
  const wrap=node('div',undefined,parent,'experiment-table-scroll diagnostic-matrix-wrap');
  const table=node('table',undefined,wrap,'experiment-table diagnostic-matrix');
  node('caption',caption,table);
  const head=node('tr',undefined,node('thead',undefined,table));
  headings.forEach(text=>{node('th',text,head).scope='col';});
  const body=node('tbody',undefined,table);
  rows.forEach(values=>{
    const row=node('tr',undefined,body);
    values.forEach((value,index)=>{
      const cell=node(index ? 'td' : 'th',String(value),row);
      if (!index) cell.scope='row';
    });
  });
  return {table,body};
}
export function renderThreshold(parent, groups, node) {
  node('h3','How often is a player this close?',parent);
  node('p','Choose a distance to see how often a player is that close to the ball in each situation.',parent,'experiment-note');
  const label=node('label','Distance from the ball (metres)',parent,'diagnostic-threshold');
  const input=node('input',undefined,label);input.type='number';input.min='0';input.step='0.5';input.value='2';
  const output=node('div',undefined,parent);output.setAttribute('aria-live','polite');
  const draw=()=>{
    output.replaceChildren();
    const value=Number(input.value);
    if(input.value === '' || !Number.isFinite(value) || value < 0) {
      node('p','Enter a distance of zero metres or more.',output,'experiment-note');return;
    }
    matrix(output,node,`Player within ${value} m of the ball`,['Reference answer','Frames within this distance','Frames measured'],Object.entries(groups).map(([state,group])=>{
      const fraction=fractionAt(group.ecdf,value);
      return [stateName(state),fraction === null ? 'No measurements' : `${(fraction*100).toFixed(1)}%`,group.samples.toLocaleString()];
    }));
  };
  input.addEventListener('input',draw);draw();
}
export function renderEventComparison(parent, frequency, node) {
  node('h3','Which events were tagged?',parent);
  node('p','Compare all tagged events with those that touch the shorter reference segment. Both bars use the same scale. The second count is included in the first; these counts do not measure accuracy.',parent,'experiment-note');
  const legend=node('div',undefined,parent,'chart-legend');
  for(const [text,className] of [['Whole recording','diagnostic-full-swatch'],['Touches reference segment','diagnostic-public-swatch']]) {
    const label=node('span',undefined,legend);node('i',undefined,label,className);node('span',text,label);
  }
  const maximum=Math.max(0,...frequency.map(row=>row.full_match));
  node('p',`All bars use a scale of 0 to ${maximum.toLocaleString()} events.`,parent,'experiment-note');
  const list=node('div',undefined,parent,'diagnostic-event-comparison');
  eventRows(frequency).forEach(row=>{
    const item=node('div',undefined,list,'diagnostic-event-row');
    node('h4',eventName(row.category),item);
    const counts=node('div',undefined,item,'diagnostic-event-counts');
    for(const [label,count,width,className] of [['Whole recording',row.full_match,row.fullWidth,'diagnostic-full-bar'],['Reference segment',row.public_overlap,row.publicWidth,'diagnostic-public-bar']]) {
      const line=node('div',undefined,counts,'diagnostic-event-measure');
      node('span',label,line);
      const track=node('span',undefined,line,'diagnostic-bar-track');track.setAttribute('aria-hidden','true');
      const bar=node('i',undefined,track,className);bar.style.width=`${width}%`;
      node('strong',count.toLocaleString(),line);
    }
  });
}
export function renderStoppageComparison(parent, events, node) {
  const s=events.stoppages;
  node('h3','Did missed stoppages have an event tag nearby?',parent);
  node('p',`The reference segment contains ${s.total.toLocaleString()} stoppages. We check for any nearby event tag, not just corners, free kicks or other set pieces.`,parent,'experiment-note');
  matrix(parent,node,'Stoppages the prediction missed in part or in full',['Event tag nearby?','Missed out of all stoppages in this group'],[
    ['Yes',rateText(s.missed_with_evidence,s.with_evidence)],
    ['No',rateText(s.missed_without_evidence,s.without_evidence)],
  ]);
  if(!s.with_evidence || !s.without_evidence) node('p','One group is empty, so we cannot compare how often stoppages were missed with and without nearby tags.',parent,'experiment-note');
}

export function renderAvailability(parent, groups, node) {
  const list=node('div',undefined,parent,'diagnostic-availability');
  Object.entries(groups).forEach(([state,g])=>{
    const row=node('div',undefined,list,'diagnostic-availability-row');
    node('strong',stateName(state),row);
    const track=node('div',undefined,row,'diagnostic-availability-track');
    track.setAttribute('role','img');
    track.setAttribute('aria-label',`${stateName(state)}: position recorded ${rateText(g.visible,g.frames)}; position missing ${rateText(g.missing,g.frames)}`);
    const visible=node('span',undefined,track,'diagnostic-observed');visible.style.width=`${g.frames ? 100*g.visible/g.frames : 0}%`;visible.style.background=states[state][1];
    node('span',g.frames ? `${(100*g.visible/g.frames).toFixed(1)}% recorded` : 'No measurements',row);
  });
  node('p','The coloured part shows frames with a ball position; the rest have no position. Each bar covers all reference frames for that situation.',parent,'experiment-note');
}
