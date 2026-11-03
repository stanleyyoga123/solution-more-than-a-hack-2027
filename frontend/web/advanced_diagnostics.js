import {teamName} from './diagnostic_copy.js';
import {states} from './diagnostic_charts.js';
import {renderECDF,renderBars} from './advanced_diagnostic_charts.js';
import {renderCases} from './diagnostic_cases.js';
import {stateName,rateText} from './diagnostic_analysis.js';
import {matrix,renderThreshold,renderEventComparison,renderStoppageComparison,renderAvailability} from './diagnostic_comparisons.js';

export function renderAdvanced(data, {section,node,plot,legend,table}, onInspect) {
  const geometry=section('Players, ball & possession','How close is the nearest player to the ball when either team has possession, or when play has stopped? These comparisons use only frames with reference answers.');
  geometry.id='diagnostics-geometry';
  if(data.geometry) {
    const groups=data.geometry.states;
    legend(geometry,['H','A','D']);
    plot(geometry,(wrap,output)=>renderECDF(wrap,groups,output));
    renderThreshold(geometry,groups,node);
    matrix(geometry,node,'Distance from the ball to the nearest player',['Reference answer','Middle distance','Frames measured / reference frames'],Object.entries(groups).map(([state,g])=>[
      stateName(state),g.median_metres === null ? 'No measurements' : `${g.median_metres.toFixed(2)} m`,`${g.samples.toLocaleString()} / ${g.frames.toLocaleString()}`,
    ]));
    node('h3','When are ball positions missing?',geometry);
    renderAvailability(geometry,groups,node);
    matrix(geometry,node,'Frames with and without a recorded ball position',['Reference answer','Position recorded','Position missing'],Object.entries(groups).map(([state,g])=>[
      stateName(state),rateText(g.visible,g.frames),rateText(g.missing,g.frames),
    ]));
    const details=node('details',undefined,geometry,'diagnostic-method');
    node('summary','How these distances are measured',details);
    table(details,['Reference answer','Frames left out'],Object.entries(groups).map(([state,g])=>[stateName(state),`${g.excluded_ball.toLocaleString()} without a ball position; ${g.excluded_players.toLocaleString()} with a ball position but no player positions`]));
    node('p','Distances are measured in metres using the pitch dimensions. We need both a ball position and at least one player position. A missing player could be nearer than those recorded. The middle distance, or median, splits the measurements into two equal halves. Tracking IDs do not reliably identify the same player throughout the recording.',details,'experiment-note');
  } else node('p','This report has no player-to-ball distances. Regenerate it with the pitch dimensions for this recording.',geometry,'chart-empty');
  node('p','Being close to the ball does not prove a player controls it, or tell us whether play has stopped.',geometry,'experiment-note');
  const events=section('Match events & stoppages','Smart Tagging automatically marks events such as corners and throw-ins. Their times are approximate. A nearby tag does not prove the possession prediction is right.');
  events.id='diagnostics-events';
  if(data.events) {
    const e=data.events;
    renderStoppageComparison(events,e,node);
    node('h3','Was play live during set-piece tags?',events);
    node('p','For frames covered by a set-piece tag, this shows the reference answer. It uses only the reference segment and counts each frame once, even when tags overlap.',events,'experiment-note');
    plot(events,(wrap,output)=>renderBars(wrap,Object.entries(e.set_piece_frames).map(([state,value])=>({label:stateName(state),value,color:states[state][1]})),output));
    renderEventComparison(events,e.frequency,node);
    const details=node('details',undefined,events,'diagnostic-method');node('summary','How nearby events and missed stoppages are counted',details);
    node('p',`A tag is nearby if it covers any part of the stoppage or the ${e.window_frames/25} seconds on either side. A stoppage counts as missed if even one of its frames is not marked as stopped, including frames with no prediction. Tag times use 25 video frames per second. Long tags can cover several stoppages.`,details,'experiment-note');
    table(details,['Team named in the tag','Events across the recording'],Object.entries(e.teams).map(([team,count])=>[teamName(team),count]));
  } else node('p','No match-event file was included in this report. Add --smart-tagging when regenerating it. You can still explore player distances and moments to review.',events,'chart-empty');
  const cases=section('Moments to review','These moments compare the prediction with the reference answers. One moment can have several issues, and several moments can relate to the same mistake.');
  cases.id='diagnostics-cases';
  if(data.failures) renderCases(cases,data.failures,node,onInspect,data.fps);
  else node('p','This report has no moments to review. Regenerate it with the current diagnostic generator.',cases,'chart-empty');
  const method=node('details',undefined,cases,'diagnostic-method');node('summary','What the review labels mean',method);
  node('p',`A missed or extra change means the prediction and reference do not have the same change within ${data.parameters?.transition_tolerance_frames ?? 'the configured number of'} frames of each other. Possible splits and joins are suggestions to check in the video, not confirmed mistakes. X means the method made no prediction. The end frame is the first frame after the moment.`,method,'experiment-note');
  if(!data.events) node('p','This report has no match-event file, so it cannot tell you whether an event was tagged nearby.',cases,'experiment-note');
}
