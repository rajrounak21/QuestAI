import { useState } from "react";
import {
  Info,
  Plane,
  Building2,
  Users,
  ExternalLink,
  BadgeCheck,
  ChevronDown,
  Sparkles,
  CircleHelp,
} from "lucide-react";
import "./travel-guide.css";

// Shared across Flights / Hotels / Trips. One-liner shown everywhere,
// full guide expands on demand. Theme comes from app CSS vars.

// Compact one-line price disclaimer. Always generic — traveler counts
// live in the booking UI itself, not in this notice.
export function PriceDisclaimer({ compact }) {
  return (
    <p className={`tg-disclaimer${compact ? " compact" : ""}`}>
      <Info size={14} aria-hidden="true" />
      <span>
        Prices are live estimates and may differ on the provider&apos;s site.
        Final price is always confirmed at checkout — please verify there before paying.
      </span>
    </p>
  );
}

const GUIDE_CONTENT = {
  flights: {
    title: "How flight booking works",
    icon: Plane,
    steps: [
      {
        icon: BadgeCheck,
        text: "Open any flight and tap Show booking options to fetch live seller prices for that exact flight.",
      },
      {
        icon: Users,
        text: "Round trip? Pick a return flight — every price shown is the full round-trip total for all travelers.",
      },
      {
        icon: ExternalLink,
        text: "Tap Book on any seller to open the airline or agent checkout in a new tab. QuestAI never charges you — you always pay the provider.",
      },
      {
        icon: Info,
        text: "Times, stops and flight numbers here always match what you'll pay for. If a seller page looks different, refresh the options — fares move fast.",
      },
    ],
  },
  hotels: {
    title: "How hotel booking works",
    icon: Building2,
    steps: [
      {
        icon: BadgeCheck,
        text: "Open any hotel and tap Book Hotel to go straight to the hotel's official site.",
      },
      {
        icon: Info,
        text: "Nightly price × nights = stay total. Taxes and fees may be added at checkout — the hotel site shows the final figure.",
      },
      {
        icon: ExternalLink,
        text: "A Free Cancel badge means free cancellation on the hotel site. Always check the rate terms before paying.",
      },
    ],
  },
  trips: {
    title: "How trip booking works",
    icon: Sparkles,
    steps: [
      {
        icon: BadgeCheck,
        text: "Plan once — flights, hotels and the day-by-day itinerary are built together for your dates and budget.",
      },
      {
        icon: Plane,
        text: "Select any flight or hotel to pin it — your budget bar re-estimates live. Booking a flight works exactly like the Flights page.",
      },
      {
        icon: Building2,
        text: "Hotel booking goes straight to the hotel's official site, same as the Hotels page.",
      },
      {
        icon: ExternalLink,
        text: "Chat follow-ups (cheaper, dates, nonstop…) only re-plan what's affected. Booking always happens on the provider's site, never here.",
      },
    ],
  },
};

// Collapsible full guide. kind: "flights" | "hotels" | "trips".
export function BookingGuide({ kind = "flights" }) {
  const [open, setOpen] = useState(false);
  const guide = GUIDE_CONTENT[kind] || GUIDE_CONTENT.flights;
  const GuideIcon = guide.icon;
  return (
    <div className="tg-guide">
      <button
        type="button"
        className="tg-guide-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="tg-guide-title">
          <GuideIcon size={16} aria-hidden="true" />
          {guide.title}
        </span>
        <span className="tg-guide-hint">{open ? "Hide" : "How it works"}</span>
        <ChevronDown size={16} aria-hidden="true" className={`tg-chevron${open ? " open" : ""}`} />
      </button>
      {open && (
        <ol className="tg-steps">
          {guide.steps.map((s, i) => (
            <li key={i} className="tg-step">
              <span className="tg-step-icon">
                <s.icon size={15} aria-hidden="true" />
              </span>
              <span>{s.text}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// Header info button (chatbot-UI pattern): opens the guide in a modal.
// Use inside .sh-top next to the other icon buttons.
export function GuideButton({ kind = "flights" }) {
  const [open, setOpen] = useState(false);
  const guide = GUIDE_CONTENT[kind] || GUIDE_CONTENT.flights;
  const GuideIcon = guide.icon;
  return (
    <>
      <button
        type="button"
        className="sh-top-btn"
        title="How booking works"
        aria-label="How booking works"
        onClick={() => setOpen(true)}
      >
        <CircleHelp size={18} aria-hidden="true" />
      </button>
      {open && (
        <div className="tg-modal-wrap" onClick={() => setOpen(false)}>
          <div className="tg-modal" onClick={(e) => e.stopPropagation()}>
            <div className="tg-modal-head">
              <span className="tg-guide-title">
                <GuideIcon size={16} aria-hidden="true" />
                {guide.title}
              </span>
              <button
                type="button"
                className="sh-top-btn"
                aria-label="Close guide"
                onClick={() => setOpen(false)}
              >
                ✕
              </button>
            </div>
            <ol className="tg-steps">
              {guide.steps.map((s, i) => (
                <li key={i} className="tg-step">
                  <span className="tg-step-icon">
                    <s.icon size={15} aria-hidden="true" />
                  </span>
                  <span>{s.text}</span>
                </li>
              ))}
            </ol>
            <PriceDisclaimer compact />
          </div>
        </div>
      )}
    </>
  );
}

export default BookingGuide;
