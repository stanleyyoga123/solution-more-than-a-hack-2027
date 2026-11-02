import {categoryName} from './diagnostic_copy.js';
/** Selected evidence context only; playback remains owned by ViewerController. */
import {intervalText,stateName} from './diagnostic_analysis.js';
export function mountInspectionContext(document, returnToDiagnostics) {
  const panel=document.querySelector('#tracking-panel');
  const banner=document.createElement('aside');banner.className='diagnostic-inspection';banner.hidden=true;
  banner.setAttribute('aria-label','Moment selected for review');
  const text=document.createElement('p');text.setAttribute('role','status');banner.append(text);
  const back=document.createElement('button');back.className='quality-button';back.textContent='Back to this moment';
  const dismiss=document.createElement('button');dismiss.className='quality-button';dismiss.textContent='Hide review note';
  banner.append(back,dismiss);panel.prepend(banner);
  let origin=null;
  back.addEventListener('click',()=>{returnToDiagnostics();origin?.focus();origin?.scrollIntoView({block:'center'});});
  dismiss.addEventListener('click',()=>{banner.hidden=true;document.querySelector('#frame-input')?.focus();});
  return {show(item,fps,trigger) {
    origin=trigger;
    text.textContent=`Reviewing: ${intervalText(item,fps)} · frames ${item.start}–${item.stop} (last frame not included). ${item.categories.map(categoryName).join(' · ')}. Reference: ${stateName(item.ground_truth)}. Prediction: ${stateName(item.predicted)}. The video will keep playing past this moment unless you pause it.`;
    banner.hidden=false;
    back.focus();
  }};
}
