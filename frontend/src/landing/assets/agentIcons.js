import aeroplaneIcon from "./aeroplane.png";
import researchIcon from "./research.png";
import shoppingCartIcon from "./shopping-cart.png";
import jobSeekerIcon from "./job-seeker.png";

// Single source for agent artwork — import from here, never re-import the PNGs.
export const AGENT_ICONS = {
  research: researchIcon,
  travel: aeroplaneIcon,
  shopping: shoppingCartIcon,
  jobs: jobSeekerIcon,
};
