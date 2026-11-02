/** Friendly display names; report keys and filtering values remain unchanged. */
const categories = {
  'False stoppage': ['Play wrongly marked as stopped', 'The reference says play was live, but the prediction says it had stopped.'],
  'Missed stoppage': ['Stoppage not picked up', 'The reference says play had stopped, but the prediction does not.'],
  'Candidate possession split': ['Possession may be split too often', 'One possession in the reference overlaps several predicted possessions. Watch the video to see whether those extra breaks make sense.'],
  'Candidate possession merge': ['Separate possessions may be joined', 'One predicted possession overlaps several possessions in the reference. It may have continued through a change that should have ended it.'],
  'Missed transition': ['Missed change in possession or play', 'A change in the reference has no matching predicted change close enough in time.'],
  'Spurious transition': ['Extra change in possession or play', 'A predicted change has no matching change in the reference close enough in time.'],
};
export const categoryName = value => categories[value]?.[0] ?? value;
export const categoryExplanation = value => categories[value]?.[1] ?? value;
export const eventName = value => ({
  'ATTACKING TRANSITION':'Moving from defence to attack',
  'DEFENSIVE TRANSITION':'Moving from attack to defence',
}[value] ?? value.charAt(0).toUpperCase()+value.slice(1).toLowerCase());
export const teamName = value => value === 'Unknown / N/A' ? 'Team not specified' : value;
