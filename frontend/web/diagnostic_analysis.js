import {categoryName} from './diagnostic_copy.js';
/** Presentation calculations on already generated evidence; no model inference. */
import {formatTime} from './viewer/timeline.js';

export const stateName = state => ({H:'Home possession (H)',A:'Away possession (A)',D:'Play stopped (D)',X:'No prediction (X)'}[state] || state);
export function rateText(count, total) {
  return total ? `${(100*count/total).toFixed(1)}% (${count.toLocaleString()} of ${total.toLocaleString()})` : 'Nothing to compare (0 of 0)';
}
export function fractionAt(points, metres) {
  if (!points.length) return null;
  let fraction = 0;
  for (const point of points) {
    if (point.metres > metres) break;
    fraction = point.fraction;
  }
  return fraction;
}
export function eventRows(frequency) {
  const maximum = Math.max(1, ...frequency.map(row=>row.full_match));
  return frequency.map(row=>({...row, fullWidth:100*row.full_match/maximum,publicWidth:100*row.public_overlap/maximum}));
}
export function orderedCases(cases, order='time') {
  return [...cases].sort((a,b)=> {
    if (order === 'duration') return (b.stop-b.start)-(a.stop-a.start) || a.start-b.start;
    if (order === 'category') return a.categories.map(categoryName).join(',').localeCompare(b.categories.map(categoryName).join(',')) || a.start-b.start;
    return a.start-b.start;
  });
}
export function intervalText(item, fps) {
  return `${formatTime(item.start/fps,true)}–${formatTime(item.stop/fps,true)} · ${((item.stop-item.start)/fps).toFixed(2)} s`;
}
