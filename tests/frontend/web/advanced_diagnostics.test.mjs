import test from 'node:test';
import assert from 'node:assert/strict';
import {filterCases, inspectCase} from '../../../frontend/web/diagnostic_cases.js';
test('filters search and overlapping categories without dropping frame zero', () => {
  const cases = [{start:0,stop:4,categories:['Missed stoppage','Missed transition'],ground_truth:'D',predicted:'H',events:[{category:'Corner',team:'Unknown / N/A'}],description:'Review timing'}];
  assert.equal(filterCases(cases, 'corner', 'Missed transition', 'D').length, 1);
  assert.equal(filterCases(cases, 'corner', 'False stoppage', '').length, 0);
  assert.equal(filterCases(cases, 'unknown', '', '').length, 1);
});
test('inspect switches tab then calls existing seek with zero-based start', () => {
  const calls=[];
  inspectCase({start:0,stop:25}, {show:name=>calls.push(name)}, {seek:frame=>calls.push(frame)});
  assert.deepEqual(calls,['tracking',0]);
});

import {renderECDF, renderBars} from '../../../frontend/web/advanced_diagnostic_charts.js';
function canvas() {
  const nodes=[];
  const document={createElementNS(_,tag){const item={tag,attrs:{},style:{},ownerDocument:document,append(){},setAttribute(k,v){this.attrs[k]=v;},addEventListener(){}};nodes.push(item);return item;}};
  return {container:{ownerDocument:document,append(){}},nodes};
}
test('ECDF preserves state stroke when inspected and keeps exact step coordinates',()=>{
  const {container,nodes}=canvas();
  renderECDF(container,{H:{samples:2,median_metres:2,ecdf:[{metres:1,fraction:.5},{metres:3,fraction:1}]}},{});
  const path=nodes.find(n=>n.tag==='path');
  assert.match(path.attrs.d,/V 140/);
  assert.match(path.attrs.style,/stroke:/);
  assert.equal(nodes.find(n=>n.tag==='svg').attrs.style,'width: 640px');
});
test('frequency bars retain true zero counts',()=>{
  const {container,nodes}=canvas();
  renderBars(container,[{label:'Corner',value:0},{label:'Free kick',value:4}],{},'Events');
  assert.deepEqual(nodes.filter(n=>n.tag==='rect').map(n=>n.attrs.width),[0,390]);
});

import {fractionAt, rateText, orderedCases, eventRows, intervalText, stateName} from '../../../frontend/web/diagnostic_analysis.js';
test('threshold readouts use right-continuous ECDF values and preserve no samples', () => {
  const points=[{metres:1,fraction:.25},{metres:2,fraction:.75},{metres:4,fraction:1}];
  assert.equal(fractionAt(points,.5),0);
  assert.equal(fractionAt(points,2),.75);
  assert.equal(fractionAt(points,9),1);
  assert.equal(fractionAt([],2),null);
});
test('rates distinguish absent denominator from observed zero',()=>{
  assert.equal(rateText(0,0),'Nothing to compare (0 of 0)');
  assert.equal(rateText(0,4),'0.0% (0 of 4)');
  assert.equal(rateText(3,4),'75.0% (3 of 4)');
});
test('event comparisons use one shared maximum and preserve original counts',()=>{
  const rows=eventRows([{category:'Corner',full_match:20,public_overlap:2},{category:'Free kick',full_match:10,public_overlap:0}]);
  assert.equal(rows[0].fullWidth,100);
  assert.equal(rows[0].publicWidth,10);
  assert.equal(rows[1].publicWidth,0);
  assert.equal(rows[1].fullWidth,50);
});
test('case sorting is stable, nonmutating, with frame zero and exclusive durations',()=>{
  const cases=[{start:0,stop:25,categories:['Missed stoppage']},{start:50,stop:150,categories:['False stoppage']}];
  assert.equal(orderedCases(cases,'duration')[0].start,50);
  assert.equal(cases[0].start,0);
  assert.equal(orderedCases(cases,'category')[0].start,50);
  assert.match(intervalText(cases[0],25),/00:00:00.000–00:00:01.000/);
  assert.match(intervalText(cases[0],25),/1.00 s/);
  assert.equal(stateName('D'),'Play stopped (D)');
});

import {categoryName, categoryExplanation} from '../../../frontend/web/diagnostic_copy.js';
test('plain case labels retain the original category for filtering and search',()=>{
  assert.equal(categoryName('Missed transition'),'Missed change in possession or play');
  assert.match(categoryExplanation('Candidate possession merge'),/may/);
  const cases=[{start:0,stop:2,categories:['Candidate possession merge'],ground_truth:'H',predicted:'A',events:[],description:'legacy description'}];
  assert.equal(filterCases(cases,'joined').length,1);
  assert.equal(filterCases(cases,'','Candidate possession merge').length,1);
  assert.equal(cases[0].categories[0],'Candidate possession merge');
});
