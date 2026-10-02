import { useState, useMemo, useEffect, useRef } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { SlidersHorizontal, Bell, LayoutGrid, User, X, Search, History, FolderOpen } from "lucide-react";
import CollapsibleSection from "./CollapsibleSection";
import { parseQuery } from "./parseQuery";
import { useRouterPrefill } from "../src/shared/useRouterPrefill";
import JobSearch from "./JobSearch";
import JobCard from "./JobCard";
import JobDetails from "./JobDetails";
import JobFilters from "./JobFilters";
import EmptyState from "./EmptyState";
import SearchProgress from "./SearchProgress";
import MissingInfoModal from "./MissingInfoModal";
import CreateAlertModal from "./CreateAlertModal";
import MyAlerts from "./MyAlerts";
import OnboardingGate from "./OnboardingGate";
import ProfilePanel from "./ProfilePanel";
import ToastContainer from "./Toast";
import { searchJobs, getProfile, getSession, getHistory, deleteSession } from "./api";
import { getToken, authFetch } from "../auth/api";
import { pushToast } from "./Toast";
import ConfirmModal from "./ConfirmModal";
import "./jobs.css";

const DEFAULT_FILTERS = { company: [], location: [], freshness: [], employment: [], sortBy: "freshness" };

const freshnessRank = { "Today": 0, "1 day ago": 1, "3 days ago": 2, "1 week ago": 3, Older: 4, Unknown: 5 };

export default function Jobs() {
  const navigate = useNavigate();
  const { sessionId: urlSessionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const autoRunRef = useRef(false);

  const [jobs, setJobs] = useState([]);
  const [total, setTotal] = useState(0);
  // Prefills for JobSearch when a saved session is restored, so the form shows
  // the roles/locations that produced these results.
  const [prefillRoles, setPrefillRoles] = useState([]);
  const [prefillLocations, setPrefillLocations] = useState([]);
  const [prefillWorkMode, setPrefillWorkMode] = useState("");
  const routerPrefill = useRouterPrefill("jobs");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [followUp, setFollowUp] = useState(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [progressSteps, setProgressSteps] = useState([]);
  const [filters, setFilters] = useState({ ...DEFAULT_FILTERS });
  const [lastQuery, setLastQuery] = useState("");
  const [selectedJob, setSelectedJob] = useState(null);
  const [showAlertModal, setShowAlertModal] = useState(false);
  const [alertModalMode, setAlertModalMode] = useState("create");
  const [editingAlert, setEditingAlert] = useState(null);
  const [alertPanelKey, setAlertPanelKey] = useState(0);
  // Lifted from MyAlerts so the header bell knows create vs edit.
  const [myAlert, setMyAlert] = useState(null);
  const alertExists = !!myAlert;
  const alertSnapshot = myAlert;
  const [accountEmail, setAccountEmail] = useState("");
  const [showProfilePanel, setShowProfilePanel] = useState(false);

  // Profile gate. null = still checking, false = needs onboarding.
  const [hasProfile, setHasProfile] = useState(null);
  const [onboardDismissed, setOnboardDismissed] = useState(false);
  // Resume-required prompt: opened when the backend replies 409 resume_required.
  const [requireResume, setRequireResume] = useState(false);
  // Search args held while the required-resume modal is open, replayed after upload.
  const pendingSearch = useRef(null);
  // Same idea for job alerts: the user asked to create or edit an alert but has
  // no resume, so the upload gate opens first and the alert form is replayed
  // once the profile lands.
  const [requireResumeForAlert, setRequireResumeForAlert] = useState(false);
  const pendingAlert = useRef(null);
  const [sessionId, setSessionId] = useState(urlSessionId || null);
  const [history, setHistory] = useState([]);
  const [deletingId, setDeletingId] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  // Controlled so the search form can fold itself once results are on screen —
  // otherwise you have to scroll past it to reach the jobs you just asked for.
  const [searchOpen, setSearchOpen] = useState(true);

  const loadHistory = async () => {
    try {
      const d = await getHistory(20);
      setHistory(d.items || []);
    } catch {
      setHistory([]);
    }
  };

  const confirmDeleteSession = (h) => setConfirmDelete(h);

  // Tapping a saved question must do exactly one thing: refill the form. It does
  // not search, and it does not leave the previous session's results sitting
  // under the new chips — that reads as "a search ran". So the stale results and
  // the session id are both dropped, which also stops the restore effect from
  // re-populating them. The user presses "Search jobs" to actually run anything.
  const prefillFromHistory = (h) => {
    setPrefillRoles(h.target_roles || []);
    setPrefillLocations(h.locations || []);
    setPrefillWorkMode(h.work_mode?.[0] || "");
    setJobs([]);
    setTotal(0);
    setFilters({ ...DEFAULT_FILTERS });
    setSelectedJob(null);
    setFollowUp(null);
    setError(null);
    setHasSearched(false);
    setSessionId(null);
    // Drop /jobs/:id from the URL so the page is plainly "not searching".
    if (urlSessionId) navigate("/jobs", { replace: true });
    setSearchOpen(true);
  };

  const doDeleteSession = async () => {
    const h = confirmDelete;
    if (!h) return;
    setConfirmDelete(null);
    setDeletingId(h.session_id);
    try {
      const res = await deleteSession(h.session_id);
      // Refresh from the server rather than trusting a local splice — the row
      // may already be gone, and the server is the source of truth.
      await loadHistory();
      // Deleting the session you're viewing drops back to a blank search page.
      if (h.session_id === sessionId) {
        setJobs([]);
        setTotal(0);
        setHasSearched(false);
        setSessionId(null);
        setProfile(null);
        navigate("/jobs", { replace: true });
      }
      pushToast(
        res?.deleted ? "Search deleted" : "Search was already removed",
        res?.deleted ? "success" : "info"
      );
    } catch (e) {
      pushToast(e.message || "Delete failed", "error");
    } finally {
      setDeletingId(null);
    }
  };

  // Restore a saved session on refresh / deep link. Jobs are persisted server
  // side, so this reads from Mongo instead of re-hitting SerpApi.
  useEffect(() => {
    if (!urlSessionId) return;
    let alive = true;
    (async () => {
      setLoading(true);
      try {
        const d = await getSession(urlSessionId);
        if (!alive) return;
        const latest = d.latest || {};
        const sess = d.session || {};
        const restored = latest.jobs || [];
        setSessionId(urlSessionId);
        setJobs(restored);
        setTotal(restored.length);
        setLastQuery(sess.query || "");
        // Re-apply the chips so the form reflects the restored session.
        if (sess.target_roles?.length) setPrefillRoles(sess.target_roles);
        if (sess.locations?.length) setPrefillLocations(sess.locations);
        if (sess.work_mode?.length) setPrefillWorkMode(sess.work_mode[0]);
        setHasSearched(true);
      } catch (e) {
        if (!alive) return;
        if (e.code === "unauthorized") {
          navigate("/login", { replace: true });
          return;
        }
        setError(e.message || "Could not load that saved search.");
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [urlSessionId, navigate]);

  useEffect(() => {
    if (!getToken()) {
      navigate("/login", { replace: true });
      return;
    }
    let alive = true;
    getProfile()
      .then((d) => {
        if (!alive) return;
        setProfile(d.profile || null);
        setHasProfile(!!d.profile);
        loadHistory();
      })
      .catch((e) => {
        if (!alive) return;
        if (e.code === "unauthorized") {
          navigate("/login", { replace: true });
          return;
        }
        // Profile lookup failed — let the user search anyway.
        setHasProfile(false);
      });

    // The alert form pre-fills the recipient from the signed-in account, so the
    // user does not have to type their own address. Best-effort: if it fails the
    // backend still defaults `email` to the account.
    authFetch("/api/auth/me")
      .then(async (r) => {
        if (!alive || !r) return;
        // authFetch returns the raw fetch Response, so .json() must be awaited.
        // Without the await, `u` is a Promise and `u.email` is always undefined,
        // which silently left the alert form's email field empty.
        const u = await r.json();
        if (alive && u && u.email) setAccountEmail(u.email);
      })
      .catch(() => {});

    return () => {
      alive = false;
    };
  }, [navigate]);

  // Stable identities for the alert modal's default props. Passing `|| []`
  // inline would allocate a new array every render, and CreateAlertModal resets
  // its chips whenever these change — which would wipe what the user typed.
  const alertRolesKey = (profile?.target_roles || []).join("|");
  const alertLocationsKey = (profile?.locations || []).join("|");
  const alertDefaultRoles = useMemo(() => profile?.target_roles || [], [alertRolesKey]);
  const alertDefaultLocations = useMemo(() => profile?.locations || [], [alertLocationsKey]);

  // Single entry point for opening the alert form, from the header bell or the
  // panel. An alert needs the stored resume (it supplies the seniority level
  // run_alert uses to drop senior-only postings), so if there is no profile we
  // park the intent, open the upload gate, and continue from its onDone.
  const requestAlert = (mode, alert = null) => {
    if (!hasProfile) {
      pendingAlert.current = { mode, alert };
      setRequireResumeForAlert(true);
      return;
    }
    setEditingAlert(alert);
    setAlertModalMode(mode);
    setShowAlertModal(true);
  };

  // Fallback for the race where the profile is deleted between the frontend
  // check and the submit: the server replies 409 and we reopen the gate.
  const onAlertResumeRequired = () => {
    setShowAlertModal(false);
    setHasProfile(false);
    pendingAlert.current = { mode: alertModalMode, alert: editingAlert };
    setRequireResumeForAlert(true);
  };

  const doSearch = async ({ query, locations, session }) => {
    setLoading(true);
    setError(null);
    setFollowUp(null);
    if (!locations) {
      setJobs([]);
      setProfile(null);
      setFilters({ ...DEFAULT_FILTERS });
    }
    setHasSearched(true);
    setProgressSteps(["Analyzing input…"]);

    if (query !== undefined) setLastQuery(query);

    try {
      // The resume is never sent here — the server reads skills from the stored
      // profile and returns 409 when there is none.
      const data = await searchJobs({
        query: query ?? lastQuery,
        locations: locations || undefined,
        sessionId: session || sessionId || undefined,
      });
      setProgressSteps(data.progress_steps || []);
      if (data.session_id) {
        setSessionId(data.session_id);
        if (data.session_id !== urlSessionId) {
          navigate(`/jobs/${data.session_id}`, { replace: true });
        }
      }
      if (data.error) setError(data.error);
      else if (data.follow_up_question) {
        setFollowUp(data.follow_up_question);
        setProfile(data.profile || null);
      } else {
        const nextJobs = data.jobs || [];
        setJobs(nextJobs);
        setTotal(data.total_results ?? nextJobs.length);
        setProfile(data.profile || null);
        loadHistory();
        // Fold the form once there is something to look at. Stays open on an
        // empty result so the user can adjust without reopening it.
        if (nextJobs.length > 0) setSearchOpen(false);
      }
    } catch (err) {
      if (err.code === "unauthorized") {
        navigate("/login", { replace: true });
        return;
      }
      // No stored skills — prompt for the resume, then replay this search.
      if (err.code === 409) {
        pendingSearch.current = { query: query ?? lastQuery, locations, session };
        setRequireResume(true);
        return;
      }
      setError(err.message || "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (obj) => doSearch(obj);

  const handleFollowUp = (payload) => {
    if (typeof payload === "string") {
      return doSearch({ query: lastQuery, locations: payload });
    }
    const nextQuery = payload.query !== undefined ? payload.query : lastQuery;
    const nextLocations = payload.locations !== undefined ? payload.locations : undefined;
    return doSearch({ query: nextQuery, locations: nextLocations });
  };

  // Deep link from the dashboard: /jobs?q=... only PREFILLS the form.
  // It used to call doSearch() here, which fired a full search on arrival — the
  // user landed on results they never asked to run. Now the question lands in
  // the form and nothing happens until they press "Search jobs" themselves.
  // The param is still stripped so a refresh can't re-prefill over their edits.
  useEffect(() => {
    const q = searchParams.get("q");
    if (!q || autoRunRef.current || urlSessionId) return;
    autoRunRef.current = true;
    setSearchParams({}, { replace: true });
    // Parse it the same way the "Try" chips are parsed, so the role, the
    // location and the work mode all land in the right fields.
    const parsed = parseQuery(q);
    // Fields the universal router already extracted win over the text parse.
    const f = routerPrefill?.fields || {};
    const roles = f.roles?.length ? f.roles : parsed.role ? [parsed.role] : [];
    const locations = f.locations?.length ? f.locations : parsed.locations;
    const mode = f.work_mode || parsed.mode || "";
    setPrefillRoles(roles);
    setPrefillLocations(locations);
    setPrefillWorkMode(mode);
    setJobs([]);
    setTotal(0);
    setHasSearched(false);
    setSearchOpen(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, urlSessionId]);

  // Shown on the collapsed Filters header so the state is visible while folded.
  const activeFilterCount = useMemo(
    () =>
      filters.company.length +
      filters.location.length +
      filters.freshness.length +
      filters.employment.length,
    [filters]
  );

  const filtered = useMemo(() => {
    let res = [...jobs];
    if (filters.company.length) res = res.filter((j) => filters.company.includes(j.company));
    if (filters.freshness.length) res = res.filter((j) => filters.freshness.includes(j.freshness_bucket || "Unknown"));
    if (filters.employment.length) res = res.filter((j) => filters.employment.includes(j.employment_type || "Not specified"));
    if (filters.location.length) {
      res = res.filter((j) => {
        const loc0 = (j.location || "Unknown").split(",")[0].trim();
        return filters.location.includes(loc0);
      });
    }
    if (filters.sortBy === "freshness") res.sort((a, b) => (freshnessRank[a.freshness_bucket] ?? 5) - (freshnessRank[b.freshness_bucket] ?? 5));
    return res;
  }, [jobs, filters]);

  // Never render nothing: a pending or failed profile check used to blank the
  // whole page, which hid real render errors.
  if (hasProfile === null) {
    return (
      <div className="app qshop">
        <header className="sh-top">
          <div className="sh-title">
            <h1>Jobs</h1>
            <span className="sh-meta">Loading your profile…</span>
          </div>
        </header>
        <main className="app-main">
          <div className="hero-empty">
            <h2>Loading your jobs…</h2>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app qshop">
      {/* Same workspace top bar as Research / Flights / Shopping / Trips.
          The grid icon on the left is the only way back to the dashboard - the
          duplicate one that used to sit on the right is gone. */}
      <header className="sh-top">
        <Link to="/home" className="sh-top-btn" title="Dashboard" aria-label="Dashboard">
          <LayoutGrid size={18} />
        </Link>
        <div className="sh-title">
          <h1>Jobs</h1>
          <span className="sh-meta">
            Google Jobs{loading ? " · searching…" : profile?.skills?.length ? ` · matched to ${profile.skills.length} saved skills` : " · fresh, personalised"}
          </span>
        </div>
        {hasProfile && (
          <button className="sh-top-btn" onClick={() => setShowProfilePanel(true)} title="Your resume" aria-label="Your resume">
            <User size={18} />
          </button>
        )}
        <button
          className="sh-top-btn"
          onClick={() => requestAlert(alertExists ? "edit" : "create", alertSnapshot)}
          title={alertExists ? "Edit your job alert" : "Create job alert"}
          aria-label={alertExists ? "Edit job alert" : "Create job alert"}
        >
          <Bell size={18} />
        </button>
      </header>

      <main className="app-main">
        {hasProfile && (
          <CollapsibleSection
            id="profile"
            icon={User}
            title="Your skills"
            defaultOpen={false}
            summary={(profile?.skills || []).length
              ? `${profile.skills.length} matched`
              : "from your resume"}
          >
            <div className="profile-bar">
              {(profile?.skills || []).slice(0, 8).map((s) => (
                <span key={s} className="profile-chip skill">
                  {s}
                </span>
              ))}
              {profile?.target_roles?.length > 0 && (
                <span className="profile-chip">{profile.target_roles.join(" / ")}</span>
              )}
              {profile?.locations?.length > 0 && (
                <span className="profile-chip loc">{profile.locations.join(", ")}</span>
              )}
            </div>
          </CollapsibleSection>
        )}

        <CollapsibleSection
          id="search"
          icon={Search}
          title="Search jobs"
          summary={lastQuery || "set a role and location"}
          open={searchOpen}
          onOpen={setSearchOpen}
        >
          <JobSearch
            onSearch={handleSearch}
            loading={loading}
            prefillRoles={prefillRoles}
            prefillLocations={prefillLocations}
            prefillWorkMode={prefillWorkMode}
          />
        </CollapsibleSection>

        {history.length > 0 && (
          <CollapsibleSection
            id="recent"
            icon={History}
            title="Recent"
            defaultOpen={false}
            summary={`${history.length} saved`}
          >
            <div className="recent-searches">
              {history.slice(0, 6).map((h) => {
                const active = h.session_id === sessionId;
                return (
                  <span key={h.session_id} className={`recent-item${active ? " active" : ""}`}>
                    {/* Tapping the question only refills the search form. It must
                        not kick off a search — reopening the saved results is
                        the separate "open" button next to it. */}
                    <button
                      type="button"
                      className="recent-chip"
                      onClick={() => prefillFromHistory(h)}
                      title={`Refill the form with "${h.title || h.query || "this search"}"`}
                    >
                      {h.title || h.query || "Search"}
                      <span className="recent-count">{h.job_count ?? 0}</span>
                    </button>
                    <button
                      type="button"
                      className="recent-open"
                      onClick={() => navigate(`/jobs/${h.session_id}`)}
                      title="Open the saved results for this search"
                      aria-label={`Open results for ${h.title || h.query || "search"}`}
                    >
                      <FolderOpen size={12} />
                    </button>
                    <button
                      type="button"
                      className="recent-del"
                      onClick={() => confirmDeleteSession(h)}
                      disabled={deletingId === h.session_id}
                      title="Delete this search"
                      aria-label={`Delete ${h.title || h.query || "search"}`}
                    >
                      {deletingId === h.session_id ? <span className="spinner-small" /> : <X size={12} />}
                    </button>
                  </span>
                );
              })}
            </div>
          </CollapsibleSection>
        )}

        {/* One alert per user: create / edit / pause / delete all live here. */}
        <MyAlerts
          key={alertPanelKey}
          onChange={setMyAlert}
          onCreate={() => requestAlert("create")}
          onEdit={(a) => requestAlert("edit", a)}
        />

        <SearchProgress loading={loading} steps={progressSteps} />

        {error && <EmptyState error={error} />}

        {followUp && (
          <MissingInfoModal
            question={followUp}
            profile={profile}
            resumeName={profile?.resume_filename || null}
            onClose={() => setFollowUp(null)}
            onSubmit={(payload) => {
              setFollowUp(null);
              handleFollowUp(payload);
            }}
            loading={loading}
          />
        )}

        {!loading && !error && !followUp && hasSearched && jobs.length === 0 && <EmptyState />}

        {!loading && jobs.length > 0 && !followUp && (
          <>
            <div className="results-container">
              <div className="results-sidebar">
                <CollapsibleSection
                  id="filters"
                  icon={SlidersHorizontal}
                  title="Filters"
                  defaultOpen={false}
                  summary={activeFilterCount ? `${activeFilterCount} active` : "none"}
                >
                  <JobFilters jobs={jobs} filters={filters} onFilterChange={setFilters} />
                </CollapsibleSection>
              </div>
              <div className="results-main">
                <div className="results-toolbar">
                  <div className="results-count">
                    <span className="count-strong">{filtered.length}</span> of {jobs.length} jobs
                    {filters.company.length || filters.location.length ? (
                      <span className="filtered-dot">• filtered</span>
                    ) : null}
                  </div>
                  <div className="toolbar-actions">
                    <span className="toolbar-label">Sort:</span>
                    <select
                      value={filters.sortBy}
                      onChange={(e) => setFilters({ ...filters, sortBy: e.target.value })}
                      className="toolbar-select"
                    >
                      <option value="freshness">Freshest first</option>
                    </select>
                  </div>
                </div>
                {filtered.length === 0 ? (
                  <div className="no-results premium">
                    <SlidersHorizontal size={16} /> No jobs match filters. Clear or adjust.
                  </div>
                ) : (
                  <div className="job-grid">
                    {filtered.map((job) => (
                      <JobCard key={job.id} job={job} onSelect={setSelectedJob} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {!hasSearched && !loading && (
          <div className="hero-empty">
            <h2>Find fresh, real jobs</h2>
            <p>
              Tell us the roles and locations you want. We fetch live Google Jobs, dedupe, sort
              freshest-first, and score each one against your saved skills.
            </p>
          </div>
        )}
      </main>

      {confirmDelete && (
        <ConfirmModal
          open
          title="Delete this search?"
          message={`"${confirmDelete.title || confirmDelete.query || "Search"}" and its saved results will be removed.`}
          confirmText="Delete"
          loading={deletingId === confirmDelete.session_id}
          onConfirm={doDeleteSession}
          onCancel={() => setConfirmDelete(null)}
        />
      )}

      {selectedJob && <JobDetails job={selectedJob} onClose={() => setSelectedJob(null)} />}

      {/* Resume gate for alerts: the user asked to create/edit an alert but has
          no stored profile. onDone resumes the parked intent. */}
      {requireResumeForAlert && (
        <OnboardingGate
          reason="alert"
          onDone={(p) => {
            setProfile(p);
            setHasProfile(true);
            setRequireResumeForAlert(false);
            const next = pendingAlert.current;
            pendingAlert.current = null;
            if (next) {
              setEditingAlert(next.alert);
              setAlertModalMode(next.mode);
              setShowAlertModal(true);
            }
          }}
        />
      )}

      {showProfilePanel && (
        <ProfilePanel
          onClose={() => setShowProfilePanel(false)}
          onChanged={(p) => {
            // Replace keeps the profile; delete clears it and re-arms onboarding.
            if (p) {
              setProfile(p);
              setHasProfile(true);
            } else {
              setProfile(null);
              setHasProfile(false);
              setOnboardDismissed(false);
              setJobs([]);
              setHasSearched(false);
            }
          }}
        />
      )}
      {showAlertModal && (
        <CreateAlertModal
          isOpen={showAlertModal}
          onClose={() => setShowAlertModal(false)}
          mode={alertModalMode}
          initial={editingAlert}
          accountEmail={accountEmail}
          defaultRoles={alertDefaultRoles}
          defaultLocations={alertDefaultLocations}
          onResumeRequired={onAlertResumeRequired}
          onSaved={() => setAlertPanelKey((k) => k + 1)}
        />
      )}
      <ToastContainer />

      {!hasProfile && !onboardDismissed && (
        <OnboardingGate
          onDone={(p) => {
            setProfile(p);
            setHasProfile(true);
            setOnboardDismissed(false);
          }}
          onSkip={() => setOnboardDismissed(true)}
        />
      )}

      {/* Backend returned 409 resume_required: upload to continue the search. */}
      {requireResume && (
        <OnboardingGate
          mode="required"
          onDone={(p) => {
            setProfile(p);
            setHasProfile(true);
            setRequireResume(false);
            const next = pendingSearch.current;
            pendingSearch.current = null;
            if (next) doSearch(next);
          }}
        />
      )}
    </div>
  );
}
