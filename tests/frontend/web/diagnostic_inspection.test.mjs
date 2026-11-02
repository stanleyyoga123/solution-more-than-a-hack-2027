import test from 'node:test';
import assert from 'node:assert/strict';
import {mountInspectionContext} from '../../../frontend/web/diagnostic_inspection.js';
function element() {return {children:[],events:{},attrs:{},append(...nodes){this.children.push(...nodes);},prepend(node){this.children.unshift(node);},setAttribute(k,v){this.attrs[k]=v;},addEventListener(k,v){this.events[k]=v;},focus(){this.focused=true;},scrollIntoView(){this.scrolled=true;}};}
test('selected context retains interval and returns focus without creating playback state',()=>{
  const panel=element(),frame=element();
  const document={createElement:element,querySelector:s=>s==='#tracking-panel'?panel:frame};
  let returns=0;
  const context=mountInspectionContext(document,()=>returns++);
  const origin=element();
  context.show({start:0,stop:25,categories:['Missed stoppage'],ground_truth:'D',predicted:'H'},25,origin);
  const banner=panel.children[0];
  assert.equal(banner.hidden,false);
  assert.match(banner.children[0].textContent,/frames 0–25 \(last frame not included\)/);
  assert.match(banner.children[0].textContent,/Play stopped \(D\)/);
  banner.children[1].events.click();assert.equal(returns,1);assert.equal(origin.focused,true);
  banner.children[2].events.click();assert.equal(banner.hidden,true);assert.equal(frame.focused,true);
});
