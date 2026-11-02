import {categoryName,categoryExplanation,eventName,teamName} from './diagnostic_copy.js';
import {stateName,intervalText,orderedCases} from './diagnostic_analysis.js';
/** Case filtering and navigation contain no independent viewer state. */
export function filterCases(cases, search = '', category = '', state = '') {
  const query = search.trim().toLowerCase();
  return cases.filter(item => (!category || item.categories.includes(category)) &&
    (!state || item.ground_truth === state) &&
    (!query || [item.start, item.stop, ...item.categories, ...item.categories.map(categoryName), ...item.categories.map(categoryExplanation), item.ground_truth, item.predicted, stateName(item.ground_truth), stateName(item.predicted),
      item.description, ...item.events.map(event => `${event.category} ${event.team}`)].join(' ').toLowerCase().includes(query)));
}
export function inspectCase(item, navigation, viewer) {
  navigation.show('tracking');
  viewer.seek(item.start);
}
export function renderCases(section, cases, node, onInspect, fps = 25) {
  const controls = node('div', undefined, section, 'diagnostic-filters');
  const field = (name, tag) => {
    const label = node('label', name, controls);
    return node(tag, undefined, label);
  };
  const search = field('Search moments', 'input'); search.type = 'search';
  const category = field('What to check', 'select');
  const state = field('Reference answer', 'select');
  const sort = field('Show moments by', 'select');
  const options = (control, pairs) => pairs.forEach(([value,label])=>{
    const option=node('option',label,control);option.value=value;
  });
  options(category,[['','All issues'],...[...new Set(cases.flatMap(item=>item.categories))].sort().map(value=>[value,categoryName(value)])]);
  options(state,[['','All reference answers'],...['H','A','D'].map(value=>[value,stateName(value)])]);
  options(sort,[['time','Earliest first'],['duration','Longest first'],['category','Issue A–Z']]);
  const clear=node('button','Clear filters',controls,'quality-button');
  const status = node('p', '', section, 'experiment-note'); status.setAttribute('aria-live','polite');
  const list = node('div', undefined, section, 'diagnostic-cases');
  const paging = node('div', undefined, section, 'diagnostic-pagination');
  const previous = node('button','Previous',paging,'quality-button');
  const next = node('button','Next',paging,'quality-button');
  let page = 0;
  function draw() {
    const filtered = orderedCases(filterCases(cases, search.value || '', category.value || '', state.value || ''),sort.value || 'time');
    list.replaceChildren();
    status.textContent = `${filtered.length.toLocaleString()} matching moments · Page ${page+1} of ${Math.max(1,Math.ceil(filtered.length/10))}. A moment can have more than one issue.`;
    filtered.slice(page*10,page*10+10).forEach(item => {
      const row = node('article',undefined,list,'diagnostic-case');
      const primary=node('div',undefined,row,'diagnostic-case-primary');
      const identity=node('div',undefined,primary);
      node('h3',intervalText(item,fps),identity);
      node('p',`Reference: ${stateName(item.ground_truth)} · Prediction: ${stateName(item.predicted)}`,identity,'diagnostic-case-state');
      node('p',item.categories.map(categoryName).join(' · '),identity,'experiment-note');
      const button=node('button','Watch in Viewer',primary,'quality-button');
      button.setAttribute('aria-label',`Watch frames ${item.start}–${item.stop} in Viewer`);
      button.addEventListener('click',()=>onInspect(item,button,fps));
      const details=node('details',undefined,row,'diagnostic-case-evidence');
      node('summary',`Details · ball tracked in ${item.ball_visibility_percent.toFixed(1)}% of frames`,details);
      node('p',`Starts at frame ${item.start.toLocaleString()} and stops just before frame ${item.stop.toLocaleString()}. Times refer to the video, not the match clock.`,details,'experiment-note');
      item.categories.forEach(category=>node('p',categoryExplanation(category),details,'experiment-note'));
      node('h4','Nearby event tags',details);
      if(!item.events.length) node('p','No nearby event tags are listed in this report.',details,'experiment-note');
      else {
        const events=node('ul',undefined,details);
        item.events.forEach(event=>node('li',`${eventName(event.category)} · ${teamName(event.team)} · ${intervalText(event,fps)}`,events));
      }
    });
    if (!filtered.length) node('p','No moments match these filters. Try clearing the filters.',list,'chart-empty');
    previous.disabled = page === 0; next.disabled = (page+1)*10 >= filtered.length;
  }
  [search,category,state,sort].forEach(control=>control.addEventListener('input',()=>{page=0;draw();}));
  clear.addEventListener('click',()=>{search.value='';category.value='';state.value='';sort.value='time';page=0;draw();search.focus();});
  previous.addEventListener('click',()=>{page--;draw();});
  next.addEventListener('click',()=>{page++;draw();});
  draw();
}
