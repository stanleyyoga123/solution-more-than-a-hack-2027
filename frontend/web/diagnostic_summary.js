import {rateText} from './diagnostic_analysis.js';

export function renderSummary(data,parent,node) {
  const overview=node('section',undefined,parent,'diagnostic-summary');
  node('h2','What to look at',overview);
  const list=node('ul',undefined,overview);
  const link=(text,target)=>{const item=node('li',undefined,list);const anchor=node('a',text,item);anchor.href=target;};
  const missing=data.frame_count-data.overview.ball_visible_frames;
  link(`The ball has no recorded position in ${rateText(missing,data.frame_count)} frames. See when tracking is missing.`, '#diagnostics-tracking');
  if(data.geometry) {
    const entries=Object.values(data.geometry.states);
    const samples=entries.reduce((sum,g)=>sum+g.samples,0);
    link(`We can measure player-to-ball distance in ${samples.toLocaleString()} of the ${data.geometry.labelled_frames.toLocaleString()} reference frames. Compare possession and stoppages.`, '#diagnostics-geometry');
  }
  if(data.events) {
    const s=data.events.stoppages;
    link(`The prediction misses at least part of ${s.missed_with_evidence+s.missed_without_evidence} of the ${s.total} reference stoppages. See which match events were recorded nearby.`, '#diagnostics-events');
  }
  if(data.failures) link(`${data.failures.length.toLocaleString()} moments are available to watch. Several may relate to the same mistake.`, '#diagnostics-cases');
  const nav=node('nav',undefined,overview,'diagnostic-section-nav');nav.setAttribute('aria-label','Diagnostic sections');
  for(const [label,target] of [['Tracking & predictions','tracking'],['Players & possession','geometry'],['Match events','events'],['Moments to review','cases']]) {
    const a=node('a',label,nav);a.href=`#diagnostics-${target}`;
  }
}
