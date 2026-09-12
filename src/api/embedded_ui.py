"""
JobsAlert Embedded Web Control Panel.
Self-contained HTML5 + Tailwind + Lucide single-page application.
Ensures the web control panel runs immediately with zero npm installation required.
"""

EMBEDDED_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>JobsAlert — Autonomous Career Intelligence Control Panel</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@latest"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: { 50: '#f0f7ff', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' }
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #030712; color: #f3f4f6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0f172a; }
    ::-webkit-scrollbar-thumb { background: #334155; border-radius: 4px; }
  </style>
</head>
<body class="min-h-screen flex flex-col">
  <!-- Top Navigation -->
  <header class="sticky top-0 z-30 bg-slate-950/90 backdrop-blur-md border-b border-slate-800/80 px-6 py-3 flex flex-wrap items-center justify-between gap-4">
    <div class="flex items-center gap-3">
      <div class="w-9 h-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-600 flex items-center justify-center text-white shadow-lg shadow-blue-500/20">
        <i data-lucide="compass" class="w-5 h-5"></i>
      </div>
      <div>
        <div class="font-extrabold text-base tracking-tight text-white flex items-center gap-2">
          JobsAlert
          <span class="text-[10px] bg-blue-950 text-blue-400 font-bold px-2 py-0.5 rounded-full border border-blue-800">
            PRO CONTROL PANEL
          </span>
        </div>
        <div class="text-xs text-slate-400">Autonomous Career Intelligence & Opportunity Scout</div>
      </div>
    </div>

    <div class="flex items-center flex-wrap gap-2.5">
      <div class="flex items-center gap-1.5 bg-slate-900 border border-slate-700/80 rounded-lg px-2.5 py-1 text-xs">
        <i data-lucide="folder-open" class="w-3.5 h-3.5 text-blue-400"></i>
        <select id="profileSelect" onchange="loadPresetProfile(this.value)" class="bg-transparent text-slate-200 text-xs focus:outline-none cursor-pointer">
          <option value="">Active Configuration</option>
        </select>
      </div>

      <button onclick="triggerRun(true)" id="btnTestRun" class="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold text-xs px-3.5 py-2 rounded-lg flex items-center gap-1.5 shadow-md transition">
        <i data-lucide="play" class="w-3.5 h-3.5 fill-white"></i> Test Run & Preview
      </button>

      <button onclick="saveConfig()" id="btnSaveConfig" class="bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 text-xs font-bold px-4 py-2 rounded-lg flex items-center gap-1.5 transition">
        <i data-lucide="save" class="w-3.5 h-3.5"></i> Save Changes
      </button>
    </div>
  </header>

  <!-- Tab Buttons -->
  <div class="bg-slate-950 border-b border-slate-800 px-6 overflow-x-auto">
    <nav class="flex space-x-1 py-2 text-xs font-semibold whitespace-nowrap" id="tabNav">
      <button onclick="switchTab('roles')" id="tabBtn-roles" class="flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 text-white transition">
        <i data-lucide="compass" class="w-4 h-4"></i> Role & Skill Matrices
      </button>
      <button onclick="switchTab('filters')" id="tabBtn-filters" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="sliders" class="w-4 h-4"></i> Filters & Rules
      </button>
      <button onclick="switchTab('watchlist')" id="tabBtn-watchlist" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="building-2" class="w-4 h-4"></i> Company Watchlist
      </button>
      <button onclick="switchTab('sources')" id="tabBtn-sources" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="globe" class="w-4 h-4"></i> Sources & ATS
      </button>
      <button onclick="switchTab('schedule')" id="tabBtn-schedule" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="clock" class="w-4 h-4"></i> Schedule & Delivery
      </button>
      <button onclick="switchTab('custom')" id="tabBtn-custom" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="plus-circle" class="w-4 h-4 text-purple-400"></i> Custom Jobs
      </button>
      <button onclick="switchTab('income')" id="tabBtn-income" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="coins" class="w-4 h-4 text-emerald-400"></i> Online Income
      </button>
      <button onclick="switchTab('dryrun')" id="tabBtn-dryrun" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="sparkles" class="w-4 h-4 text-amber-400"></i> Dry-Run & Email Preview
      </button>
      <button onclick="switchTab('health')" id="tabBtn-health" class="flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition">
        <i data-lucide="activity" class="w-4 h-4 text-emerald-400"></i> Health & Logs
      </button>
    </nav>
  </div>

  <!-- Main Container -->
  <main class="flex-1 max-w-7xl w-full mx-auto p-6">
    <!-- Toast Notification -->
    <div id="toast" class="hidden fixed bottom-6 right-6 bg-emerald-600 text-white text-sm font-semibold px-4 py-2.5 rounded-lg shadow-xl flex items-center gap-2 z-50 transition">
      <i data-lucide="check-circle-2" class="w-4 h-4"></i> <span id="toastMsg">Saved!</span>
    </div>

    <!-- 1. ROLES TAB -->
    <div id="tab-roles" class="space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="briefcase" class="w-4 h-4 text-blue-400"></i> Target Roles & Titles
        </h2>
        <p class="text-xs text-slate-400 mb-4">The scoring engine evaluates postings matching these exact roles or adjacent specializations.</p>
        <div class="flex gap-2 mb-3">
          <input id="inputRole" type="text" placeholder="e.g. Staff Distributed Systems Engineer" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-blue-500">
          <button onclick="addRole()" class="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Role</button>
        </div>
        <div id="rolesList" class="flex flex-wrap gap-2"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="check-circle-2" class="w-4 h-4 text-emerald-400"></i> Must-Have Technical Skills
        </h2>
        <p class="text-xs text-slate-400 mb-4">Postings missing these skills receive steep score deductions.</p>
        <div class="flex gap-2 mb-3">
          <input id="inputMust" type="text" placeholder="e.g. Go, Kubernetes, Kafka" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500">
          <button onclick="addSkill('must')" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Skill</button>
        </div>
        <div id="mustList" class="flex flex-wrap gap-2"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="star" class="w-4 h-4 text-amber-400"></i> Nice-to-Have Skills (Bonus Points)
        </h2>
        <p class="text-xs text-slate-400 mb-4">Secondary technologies that grant bonus scores and trigger 9.0+ immediate alerts.</p>
        <div class="flex gap-2 mb-3">
          <input id="inputNice" type="text" placeholder="e.g. Rust, WebAssembly, Edge AI" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-amber-500">
          <button onclick="addSkill('nice')" class="bg-amber-600 hover:bg-amber-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Bonus</button>
        </div>
        <div id="niceList" class="flex flex-wrap gap-2"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="ban" class="w-4 h-4 text-red-400"></i> Excluded Terms (Negative Keywords)
        </h2>
        <p class="text-xs text-slate-400 mb-4">Any posting containing these terms will be immediately dropped to Score 0.0.</p>
        <div class="flex gap-2 mb-3">
          <input id="inputExcluded" type="text" placeholder="e.g. PHP, WordPress, No C2C" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-red-500">
          <button onclick="addSkill('excluded')" class="bg-red-600 hover:bg-red-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Excluded</button>
        </div>
        <div id="excludedList" class="flex flex-wrap gap-2"></div>
      </div>
    </div>

    <!-- 2. FILTERS TAB -->
    <div id="tab-filters" class="hidden space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
            <i data-lucide="award" class="w-4 h-4 text-indigo-400"></i> Experience Level
          </h2>
          <label class="text-xs text-slate-400 block mb-1">Candidate Name / Identifier</label>
          <input id="candidateName" type="text" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white mb-4">

          <div class="flex justify-between text-xs text-slate-400 mb-1">
            <span>Years of Relevant Experience</span>
            <span id="expYearsVal" class="text-indigo-400 font-bold">6 Years</span>
          </div>
          <input id="expYears" type="range" min="1" max="20" class="w-full h-2 bg-slate-800 rounded-lg accent-indigo-500" oninput="document.getElementById('expYearsVal').innerText = this.value + ' Years'">
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
            <i data-lucide="dollar-sign" class="w-4 h-4 text-amber-400"></i> Salary Floor & Compensation
          </h2>
          <label class="text-xs text-slate-400 block mb-1">Minimum Base Salary (USD / year)</label>
          <input id="salaryFloor" type="number" step="5000" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white font-mono mb-4">
          <div class="p-2.5 bg-slate-950 rounded-lg border border-slate-800 text-[11px] text-slate-400">
            • Postings with transparent comp above floor earn high bonus.<br>
            • Postings with unlisted comp are scored neutrally without penalty.
          </div>
        </div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-2 flex items-center gap-2">
          <i data-lucide="map-pin" class="w-4 h-4 text-emerald-400"></i> Preferred Locations & Remote Scope
        </h2>
        <div class="flex gap-2 mb-3">
          <input id="inputLoc" type="text" placeholder="e.g. Remote, Worldwide, United States" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
          <button onclick="addLocation()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Location</button>
        </div>
        <div id="locationsList" class="flex flex-wrap gap-2"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-2 flex items-center gap-2">
          <i data-lucide="shield-check" class="w-4 h-4 text-emerald-400"></i> Automated Job Link Verification
        </h2>
        <p class="text-xs text-slate-400 mb-4">
          Automatically checks all job URLs to ensure postings are active and have not expired or closed.
        </p>
        <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <div>
              <span class="text-xs font-bold text-white">Enable Link Verification</span>
              <div class="text-[11px] text-slate-400">Drop dead links (404/410/closed)</div>
            </div>
            <input id="chkLinkVerify" type="checkbox" class="w-4 h-4 accent-emerald-500">
          </label>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Timeout (Seconds)</label>
            <input id="verifyTimeout" type="number" step="0.5" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white">
          </div>
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <div>
              <span class="text-xs font-bold text-white">Detect Soft-404 Pages</span>
              <div class="text-[11px] text-slate-400">Inspect for 'position closed' text</div>
            </div>
            <input id="chkSoft404" type="checkbox" class="w-4 h-4 accent-emerald-500">
          </label>
        </div>
      </div>
    </div>

    <!-- 3. WATCHLIST TAB -->

    <div id="tab-watchlist" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="building-2" class="w-4 h-4 text-amber-400"></i> Priority Watchlist Companies
        </h2>
        <p class="text-xs text-slate-400 mb-4">Dream employers receive priority multipliers on their company score.</p>
        <div class="flex gap-2 mb-4">
          <input id="watchName" type="text" placeholder="e.g. Cloudflare" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
          <select id="watchMult" class="bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
            <option value="1.15">1.15x Boost</option>
            <option value="1.20">1.20x Boost</option>
            <option value="1.25" selected>1.25x Boost</option>
            <option value="1.30">1.30x Boost</option>
            <option value="1.50">1.50x Boost</option>
          </select>
          <button onclick="addWatchlist()" class="bg-amber-600 hover:bg-amber-500 text-white px-4 py-1.5 rounded-lg text-xs font-semibold">Add</button>
        </div>
        <div id="watchlistGrid" class="grid grid-cols-1 md:grid-cols-3 gap-3"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-1 flex items-center gap-2">
          <i data-lucide="shield-alert" class="w-4 h-4 text-red-400"></i> Excluded Companies (Blacklist)
        </h2>
        <p class="text-xs text-slate-400 mb-4">Staffing agencies and recruiters to discard immediately.</p>
        <div class="flex gap-2 mb-4">
          <input id="blacklistName" type="text" placeholder="e.g. CyberCoders, Revature" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
          <button onclick="addBlacklist()" class="bg-red-600 hover:bg-red-500 text-white px-4 py-1.5 rounded-lg text-xs font-semibold">Add Blacklist</button>
        </div>
        <div id="blacklistGrid" class="flex flex-wrap gap-2"></div>
      </div>
    </div>

    <!-- 4. SOURCES TAB -->
    <div id="tab-sources" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
          <i data-lucide="layers" class="w-4 h-4 text-emerald-400"></i> Direct Verified ATS Boards
        </h2>
        <div class="space-y-4" id="atsSources">
          <div class="bg-slate-950 border border-slate-800 p-3 rounded-lg">
            <div class="flex justify-between items-center mb-2">
              <span class="font-bold text-xs text-white">Greenhouse Public Boards API</span>
              <input id="chkGreenhouse" type="checkbox" class="w-4 h-4 accent-emerald-500">
            </div>
            <input id="greenhouseSlugs" type="text" placeholder="cloudflare, datadog, figma, elastic" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-mono">
          </div>

          <div class="bg-slate-950 border border-slate-800 p-3 rounded-lg">
            <div class="flex justify-between items-center mb-2">
              <span class="font-bold text-xs text-white">Lever Postings API</span>
              <input id="chkLever" type="checkbox" class="w-4 h-4 accent-blue-500">
            </div>
            <input id="leverSlugs" type="text" placeholder="netflix, atlassian, palantir" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-mono">
          </div>

          <div class="bg-slate-950 border border-slate-800 p-3 rounded-lg">
            <div class="flex justify-between items-center mb-2">
              <span class="font-bold text-xs text-white">Ashby Posting API</span>
              <input id="chkAshby" type="checkbox" class="w-4 h-4 accent-purple-500">
            </div>
            <input id="ashbySlugs" type="text" placeholder="linear, ramp, retool, openai" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white font-mono">
          </div>
        </div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
          <i data-lucide="globe" class="w-4 h-4 text-cyan-400"></i> Remote Job Aggregators & Feeds
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <span class="text-xs font-bold text-white">Remotive Remote API</span>
            <input id="chkRemotive" type="checkbox" class="w-4 h-4 accent-cyan-500">
          </label>
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <span class="text-xs font-bold text-white">RemoteOK API</span>
            <input id="chkRemoteOK" type="checkbox" class="w-4 h-4 accent-cyan-500">
          </label>
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <span class="text-xs font-bold text-white">Arbeitnow API</span>
            <input id="chkArbeitnow" type="checkbox" class="w-4 h-4 accent-cyan-500">
          </label>
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between cursor-pointer">
            <span class="text-xs font-bold text-white">Jobicy Remote API</span>
            <input id="chkJobicy" type="checkbox" class="w-4 h-4 accent-cyan-500">
          </label>
          <label class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex items-center justify-between md:col-span-2 cursor-pointer">
            <div>
              <span class="text-xs font-bold text-orange-400">Hacker News 'Who is Hiring?' (Algolia)</span>
              <div class="text-[11px] text-slate-400">Monthly high-signal startup hiring thread</div>
            </div>
            <input id="chkHN" type="checkbox" class="w-4 h-4 accent-orange-500">
          </label>
          <div class="bg-slate-950 border border-slate-800 p-4 rounded-lg md:col-span-2 space-y-3">
            <div class="flex items-center justify-between">
              <div>
                <span class="text-xs font-bold text-sky-400 flex items-center gap-1.5">
                  <i data-lucide="twitter" class="w-4 h-4"></i> Twitter / X Job Scout
                </span>
                <div class="text-[11px] text-slate-400">Scout hiring tweets, hashtags, and recruitment handles</div>
              </div>
              <input id="chkTwitter" type="checkbox" class="w-4 h-4 accent-sky-500">
            </div>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
              <div>
                <label class="text-[11px] text-slate-400 block mb-1">Search Queries / Hashtags (comma-separated)</label>
                <input id="twitterQueries" type="text" placeholder="e.g. #hiring #remotejobs, remote hiring" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white">
              </div>
              <div>
                <label class="text-[11px] text-slate-400 block mb-1">Monitored Twitter Handles (comma-separated)</label>
                <input id="twitterAccounts" type="text" placeholder="e.g. TechJobsAfrica, RemoteJobs, JobbermanOnline" class="w-full bg-slate-900 border border-slate-700 rounded px-2.5 py-1 text-xs text-white">
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>


    <!-- 5. SCHEDULE TAB -->
    <div id="tab-schedule" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
          <i data-lucide="clock" class="w-4 h-4 text-blue-400"></i> Timing & Automation Schedules
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="text-xs text-slate-400 block mb-1">Timezone</label>
            <input id="schedTz" type="text" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Daily Digest Delivery Time</label>
            <input id="schedTime" type="time" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white font-mono">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Weekly Digest Day</label>
            <input id="schedDay" type="text" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Immediate Alert Score Threshold</label>
            <input id="schedInstant" type="number" step="0.1" min="8.0" max="10.0" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white font-mono">
          </div>
        </div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
          <i data-lucide="mail" class="w-4 h-4 text-indigo-400"></i> Email Delivery Provider
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label class="text-xs text-slate-400 block mb-1">Provider</label>
            <select id="delivProvider" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white">
              <option value="resend">Resend (Default 3,000 free/mo)</option>
              <option value="brevo">Brevo (300 free/day)</option>
              <option value="sendgrid">SendGrid</option>
              <option value="smtp">Custom SMTP</option>
              <option value="console">Console / Preview Only</option>
            </select>
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Recipient Email</label>
            <input id="delivEmail" type="email" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white">
          </div>
        </div>
      </div>
    </div>

    <!-- 6. CUSTOM JOBS TAB -->
    <div id="tab-custom" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <h2 class="text-base font-bold text-white mb-2 flex items-center gap-2">
          <i data-lucide="plus-circle" class="w-4 h-4 text-purple-400"></i> Manually Enter a Custom Job Posting
        </h2>
        <p class="text-xs text-slate-400 mb-6">
          Paste an opportunity found on LinkedIn, X/Twitter, a personal referral, or direct email. The engine will parse, score, and rank it alongside automated sources and include it in your email alerts.
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
          <div>
            <label class="text-xs text-slate-400 block mb-1">Job Title *</label>
            <input id="cjTitle" type="text" placeholder="e.g. Staff Distributed Systems Engineer" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Company Name *</label>
            <input id="cjCompany" type="text" placeholder="e.g. Anthropic, OpenAI, Stripe" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Location & Remote Policy</label>
            <input id="cjLocation" type="text" placeholder="e.g. Worldwide Remote or San Francisco (Hybrid)" value="Worldwide Remote" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Application URL</label>
            <input id="cjUrl" type="url" placeholder="https://..." class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Salary Min ($ / yr)</label>
            <input id="cjSalaryMin" type="number" step="5000" placeholder="e.g. 180000" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500">
          </div>
          <div>
            <label class="text-xs text-slate-400 block mb-1">Salary Max ($ / yr)</label>
            <input id="cjSalaryMax" type="number" step="5000" placeholder="e.g. 240000" class="w-full bg-slate-950 border border-slate-700 rounded px-3 py-1.5 text-xs text-white font-mono focus:outline-none focus:border-purple-500">
          </div>
          <div class="md:col-span-2">
            <label class="text-xs text-slate-400 block mb-1">Description / Key Technical Requirements</label>
            <textarea id="cjDesc" rows="3" placeholder="Paste the job description, required tech stack (Go, Kubernetes, etc.) or notes..." class="w-full bg-slate-950 border border-slate-700 rounded p-2.5 text-xs text-white focus:outline-none focus:border-purple-500"></textarea>
          </div>
        </div>

        <button onclick="submitCustomJob()" class="bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold px-4 py-2 rounded-lg flex items-center gap-1.5 transition">
          <i data-lucide="plus" class="w-3.5 h-3.5"></i> Save & Queue Custom Job
        </button>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-sm">
        <div class="flex justify-between items-center mb-3">
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="list" class="w-4 h-4 text-purple-400"></i> Your Manually Entered Jobs
          </h2>
          <button onclick="loadCustomJobs()" class="text-xs text-slate-400 hover:text-white flex items-center gap-1">
            <i data-lucide="refresh-cw" class="w-3 h-3"></i> Refresh
          </button>
        </div>
        <div id="customJobsList" class="space-y-3">
          <div class="text-xs text-slate-500">Loading custom jobs...</div>
        </div>
      </div>
    </div>

    <!-- ONLINE INCOME TAB -->
    <div id="tab-income" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 flex flex-wrap justify-between items-center gap-3">
        <div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="coins" class="w-4 h-4 text-emerald-400"></i> Online Income Opportunities & Flexible Gigs
          </h2>
          <p class="text-xs text-slate-400">Legitimate remote work: AI evaluation, tutoring, proofreading, transcription, user testing & research.</p>
        </div>

        <div class="flex items-center gap-2">
          <button onclick="triggerIncomeRun(true)" id="btnScanIncome" class="bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-bold text-xs px-3.5 py-2 rounded-lg flex items-center gap-1.5 shadow-md transition">
            <i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Scan Online Income
          </button>
          <button onclick="setIncomeSubTab('cards')" id="btnIncomeSubCards" class="bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">
            Opportunity Tracks
          </button>
          <button onclick="setIncomeSubTab('email')" id="btnIncomeSubEmail" class="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold">
            HTML Email Preview
          </button>
          <button onclick="setIncomeSubTab('settings')" id="btnIncomeSubSettings" class="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold">
            Preferences
          </button>
          <button onclick="setIncomeSubTab('custom')" id="btnIncomeSubCustom" class="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold">
            Custom Gigs
          </button>
        </div>
      </div>

      <!-- Quality, Side-Job Fit & Trust Tier Filter Controls -->
      <div class="bg-slate-900/90 border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div class="flex flex-wrap items-center gap-3">
          <div class="flex items-center gap-1.5">
            <span class="text-slate-400 font-semibold flex items-center gap-1"><i data-lucide="shield-check" class="w-3.5 h-3.5 text-emerald-400"></i> Quality:</span>
            <select id="selIncomeMinQuality" onchange="loadIncomeOpportunities()" class="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2 py-1 focus:outline-none">
              <option value="7.0">Quality Gated (≥ 7.0)</option>
              <option value="8.5">Top-Tier Only (≥ 8.5)</option>
              <option value="0.0">All Quality Scores</option>
            </select>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-slate-400 font-semibold flex items-center gap-1"><i data-lucide="moon" class="w-3.5 h-3.5 text-indigo-400"></i> Side-Job Fit:</span>
            <select id="selIncomeSideJobFit" onchange="loadIncomeOpportunities()" class="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2 py-1 focus:outline-none">
              <option value="0.0">All Schedules</option>
              <option value="7.0">High Side-Job Fit (≥ 7.0)</option>
              <option value="9.0">100% Asynchronous Only (≥ 9.0)</option>
            </select>
          </div>

          <div class="flex items-center gap-1.5">
            <span class="text-slate-400 font-semibold flex items-center gap-1"><i data-lucide="award" class="w-3.5 h-3.5 text-amber-400"></i> Trust Tier:</span>
            <select id="selIncomeTrustTier" onchange="loadIncomeOpportunities()" class="bg-slate-950 border border-slate-700 text-slate-200 text-xs rounded px-2 py-1 focus:outline-none">
              <option value="">All Verified Tiers</option>
              <option value="tier_1">Tier 1 Highest (Official Portals)</option>
              <option value="tier_2">Tier 2 Good (Established Platforms)</option>
            </select>
          </div>
        </div>

        <div class="flex items-center gap-2">
          <label class="flex items-center gap-1.5 text-slate-400 cursor-pointer hover:text-slate-200 text-xs">
            <input type="checkbox" id="chkShowRejectedIncome" onchange="loadIncomeOpportunities()" class="rounded bg-slate-950 border-slate-700 text-red-500 focus:ring-0">
            <span>Show Gated / Discarded</span>
          </label>
        </div>
      </div>

      <!-- Category Filter Pills -->
      <div id="incomeCategoryPills" class="flex flex-wrap gap-2 text-xs">
        <button onclick="filterIncomeCategory('')" class="income-cat-pill bg-emerald-950 border border-emerald-700 text-emerald-300 px-3 py-1 rounded-full font-semibold">All Categories</button>
        <button onclick="filterIncomeCategory('ai_evaluation')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">AI Evaluation & Training</button>
        <button onclick="filterIncomeCategory('data_annotation')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Data Annotation</button>
        <button onclick="filterIncomeCategory('academic_editing')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Academic Editing</button>
        <button onclick="filterIncomeCategory('research')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Research & Studies</button>
        <button onclick="filterIncomeCategory('user_testing')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">User Testing & UX</button>
        <button onclick="filterIncomeCategory('tutoring')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Online Tutoring</button>
        <button onclick="filterIncomeCategory('transcription')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Transcription</button>
        <button onclick="filterIncomeCategory('virtual_assistant')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Virtual Assistant</button>
        <button onclick="filterIncomeCategory('customer_support')" class="income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full">Customer Support</button>
      </div>

      <!-- 1. Cards View -->
      <div id="incomeCardsView" class="space-y-3"></div>

      <!-- 2. Email Preview View -->
      <div id="incomeEmailView" class="hidden bg-slate-900 border border-slate-800 rounded-xl p-2">
        <iframe id="incomeEmailIframe" src="/api/income/preview-email" class="w-full h-[700px] border-0 rounded-lg bg-slate-950"></iframe>
      </div>

      <!-- 3. Preferences View -->
      <div id="incomeSettingsView" class="hidden space-y-6">
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <i data-lucide="map-pin" class="w-4 h-4 text-emerald-400"></i> Country & Location Eligibility
          </h3>
          <p class="text-xs text-slate-400 mb-3">Include countries/regions where you reside to match location requirements.</p>
          <div class="flex gap-2 mb-3">
            <input id="incomeInputCountry" type="text" placeholder="e.g. Nigeria, Worldwide, Africa, United Kingdom" class="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-emerald-500">
            <button onclick="addIncomeCountry()" class="bg-emerald-600 hover:bg-emerald-500 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">Add Region</button>
          </div>
          <div id="incomeCountriesList" class="flex flex-wrap gap-2"></div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <i data-lucide="dollar-sign" class="w-4 h-4 text-amber-400"></i> Minimum Hourly Pay Floor (USD)
          </h3>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Floor ($/hr)</label>
              <input id="incomeMinRate" type="number" step="0.5" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
            </div>
            <div>
              <label class="block text-xs font-semibold text-slate-300 mb-1">Max Weekly Hours</label>
              <input id="incomeMaxHours" type="number" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-white">
            </div>
          </div>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 class="text-sm font-bold text-white mb-3 flex items-center gap-2">
            <i data-lucide="shield-check" class="w-4 h-4 text-cyan-400"></i> Platform Sources & Verification
          </h3>
          <div class="space-y-3 text-xs">
            <label class="flex items-center gap-2.5 text-slate-200">
              <input type="checkbox" id="chkIncomeLinkVerify" class="rounded bg-slate-950 border-slate-700 text-emerald-600 focus:ring-0">
              <span><strong>Enforce Live Link & Scam Verification:</strong> Drop dead links and scam signatures immediately.</span>
            </label>
            <label class="flex items-center gap-2.5 text-slate-200">
              <input type="checkbox" id="chkIncomeAiEval" class="rounded bg-slate-950 border-slate-700 text-emerald-600 focus:ring-0">
              <span>AI Evaluation & Annotation Platforms (DataAnnotation, Outlier, OneForma, TELUS, Appen)</span>
            </label>
            <label class="flex items-center gap-2.5 text-slate-200">
              <input type="checkbox" id="chkIncomeUserTesting" class="rounded bg-slate-950 border-slate-700 text-emerald-600 focus:ring-0">
              <span>User Testing & Research Studies (UserTesting, Testbirds, Respondent, Prolific)</span>
            </label>
            <label class="flex items-center gap-2.5 text-slate-200">
              <input type="checkbox" id="chkIncomeAcademic" class="rounded bg-slate-950 border-slate-700 text-emerald-600 focus:ring-0">
              <span>Academic Proofreading & Online Tutoring (Cambridge, Scribbr, Preply, Cambly)</span>
            </label>
            <label class="flex items-center gap-2.5 text-slate-200">
              <input type="checkbox" id="chkIncomeSupport" class="rounded bg-slate-950 border-slate-700 text-emerald-600 focus:ring-0">
              <span>Transcription, Virtual Assistant & Remote Support (Rev, GoTranscript, ModSquad, Belay)</span>
            </label>
          </div>
          <div class="mt-4">
            <button onclick="saveIncomeConfig()" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-4 py-2 rounded-lg text-xs flex items-center gap-2">
              <i data-lucide="save" class="w-3.5 h-3.5"></i> Save Online Income Preferences
            </button>
          </div>
        </div>
      </div>

      <!-- 4. Custom Gigs View -->
      <div id="incomeCustomView" class="hidden space-y-6">
        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h3 class="text-sm font-bold text-white mb-2 flex items-center gap-2">
            <i data-lucide="plus-circle" class="w-4 h-4 text-emerald-400"></i> Add Custom Online Income Gig
          </h3>
          <p class="text-xs text-slate-400 mb-4">Add legitimate online micro-work, freelance tracks, or platform listings to evaluate and track.</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Opportunity Title *</label>
              <input id="customIncTitle" type="text" placeholder="e.g. Remote Financial Data Annotator" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
            </div>
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Platform / Organization *</label>
              <input id="customIncOrg" type="text" placeholder="e.g. Outlier AI / Telus" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
            </div>
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Category</label>
              <select id="customIncCat" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
                <option value="ai_evaluation">AI Evaluation & Training</option>
                <option value="data_annotation">Data Annotation</option>
                <option value="user_testing">User Testing</option>
                <option value="survey_research">Survey / Research Study</option>
                <option value="academic_proofreading">Academic Proofreading</option>
                <option value="online_tutoring">Online Tutoring</option>
                <option value="transcription">Transcription</option>
                <option value="virtual_assistant">Virtual Assistant</option>
                <option value="bookkeeping">Bookkeeping</option>
                <option value="remote_support">Remote Support</option>
                <option value="general_flexible">General Flexible Work</option>
              </select>
            </div>
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Pay Rate Display</label>
              <input id="customIncPayDisplay" type="text" placeholder="e.g. $20–$30/hr or $15/test" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
            </div>
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Application URL</label>
              <input id="customIncUrl" type="url" placeholder="https://example.com/apply" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
            </div>
            <div>
              <label class="block text-slate-300 font-semibold mb-1">Location / Country Eligibility</label>
              <input id="customIncLocation" type="text" placeholder="Worldwide / Nigeria Eligible" class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white">
            </div>
            <div class="sm:col-span-2">
              <label class="block text-slate-300 font-semibold mb-1">Description</label>
              <textarea id="customIncDesc" rows="2" placeholder="Task description, payout methods, requirements..." class="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-1.5 text-white"></textarea>
            </div>
          </div>
          <button onclick="submitCustomIncome()" class="mt-4 bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-4 py-2 rounded-lg text-xs flex items-center gap-1.5">
            <i data-lucide="plus" class="w-3.5 h-3.5"></i> Add Income Opportunity
          </button>
        </div>

        <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
          <div class="flex justify-between items-center mb-3">
            <h3 class="text-sm font-bold text-white flex items-center gap-2">
              <i data-lucide="list" class="w-4 h-4 text-emerald-400"></i> Manually Added Custom Gigs
            </h3>
            <button onclick="loadCustomIncomeList()" class="text-slate-400 hover:text-white text-xs flex items-center gap-1">
              <i data-lucide="refresh-cw" class="w-3 h-3"></i> Refresh
            </button>
          </div>
          <div id="customIncomeList" class="space-y-3">
            <div class="text-xs text-slate-500">Loading custom opportunities...</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 7. DRY-RUN TAB -->
    <div id="tab-dryrun" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-4 flex justify-between items-center">
        <div>
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="sparkles" class="w-4 h-4 text-amber-400"></i> Scored Job Opportunities & Email Preview
          </h2>
        </div>

        <div class="flex gap-2">
          <button onclick="setDryRunSubTab('cards')" id="btnSubCards" class="bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold">
            Job Cards
          </button>
          <button onclick="setDryRunSubTab('email')" id="btnSubEmail" class="bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold">
            HTML Email Preview
          </button>
        </div>
      </div>

      <div id="dryRunCardsView" class="space-y-3"></div>
      <div id="dryRunEmailView" class="hidden bg-slate-900 border border-slate-800 rounded-xl p-2">
        <iframe src="/api/preview-email" class="w-full h-[700px] border-0 rounded-lg bg-slate-950"></iframe>
      </div>
    </div>

    <!-- 7. HEALTH TAB -->
    <div id="tab-health" class="hidden space-y-6">
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <div class="flex justify-between items-center mb-4">
          <h2 class="text-base font-bold text-white flex items-center gap-2">
            <i data-lucide="activity" class="w-4 h-4 text-emerald-400"></i> Crawler Latency & Connector Status
          </h2>
          <button onclick="clearCache()" class="bg-red-950 border border-red-800 text-red-300 px-3 py-1 rounded text-xs font-semibold hover:bg-red-900">
            Clear Deduplication Cache
          </button>
        </div>
        <div id="healthContainer" class="grid grid-cols-1 sm:grid-cols-3 gap-3"></div>
      </div>

      <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
        <h2 class="text-base font-bold text-white mb-4 flex items-center gap-2">
          <i data-lucide="clock" class="w-4 h-4 text-indigo-400"></i> Historical Execution Runs
        </h2>
        <div id="logsContainer" class="text-xs text-slate-400">Loading logs...</div>
      </div>
    </div>
  </main>

  <footer class="border-t border-slate-800 px-6 py-4 text-center text-xs text-slate-500">
    JobsAlert Autonomous Career Intelligence • 100% Free Open Infrastructure
  </footer>

  <script>
    let appConfig = null;

    async function init() {
      const res = await fetch('/api/config');
      appConfig = await res.json();
      renderAll();

      const pRes = await fetch('/api/profiles');
      const pData = await pRes.json();
      const sel = document.getElementById('profileSelect');
      (pData.profiles || []).forEach(p => {
        const opt = document.createElement('option');
        opt.value = p;
        opt.innerText = 'Profile: ' + p;
        sel.appendChild(opt);
      });

      lucide.createIcons();
    }

    function switchTab(tabId) {
      ['roles', 'filters', 'watchlist', 'sources', 'schedule', 'custom', 'income', 'dryrun', 'health'].forEach(t => {
        document.getElementById('tab-' + t).classList.add('hidden');
        document.getElementById('tabBtn-' + t).className = 'flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition';
      });
      document.getElementById('tab-' + tabId).classList.remove('hidden');
      document.getElementById('tabBtn-' + tabId).className = 'flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 text-white transition';
      if (tabId === 'health') loadTelemetry();
      if (tabId === 'custom') loadCustomJobs();
      if (tabId === 'income') {
        loadIncomeOpportunities();
        loadCustomIncomeList();
      }
      lucide.createIcons();
    }

    async function submitCustomJob() {
      const title = document.getElementById('cjTitle').value.trim();
      const company = document.getElementById('cjCompany').value.trim();
      const location = document.getElementById('cjLocation').value.trim() || 'Worldwide Remote';
      const url = document.getElementById('cjUrl').value.trim();
      const salary_min = parseFloat(document.getElementById('cjSalaryMin').value) || null;
      const salary_max = parseFloat(document.getElementById('cjSalaryMax').value) || null;
      const description = document.getElementById('cjDesc').value.trim();

      if (!title || !company) {
        alert('Please provide at least a Job Title and Company Name.');
        return;
      }

      const res = await fetch('/api/jobs/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, company, location, url, salary_min, salary_max, description })
      });
      if (res.ok) {
        showToast('Custom job added successfully!');
        document.getElementById('cjTitle').value = '';
        document.getElementById('cjCompany').value = '';
        document.getElementById('cjUrl').value = '';
        document.getElementById('cjSalaryMin').value = '';
        document.getElementById('cjSalaryMax').value = '';
        document.getElementById('cjDesc').value = '';
        loadCustomJobs();
      }
    }

    async function loadCustomJobs() {
      const res = await fetch('/api/jobs/custom');
      const data = await res.json();
      const list = data.custom_jobs || [];
      const cont = document.getElementById('customJobsList');
      if (!list || list.length === 0) {
        cont.innerHTML = '<div class="text-xs text-slate-500">No custom jobs entered yet. Enter one above to score and track it!</div>';
        return;
      }
      cont.innerHTML = list.map((job, idx) => `
        <div class="bg-slate-950 border border-slate-800 p-3.5 rounded-lg flex justify-between items-start text-xs">
          <div>
            <div class="font-bold text-white text-sm">${job.title}</div>
            <div class="text-purple-400 font-semibold mt-0.5">${job.company} • <span class="text-slate-400">${job.location}</span></div>
            ${job.description ? `<p class="text-slate-400 mt-1.5 line-clamp-2">${job.description}</p>` : ''}
            ${job.salary_min || job.salary_max ? `<div class="text-amber-400 font-mono font-semibold mt-1.5">💰 $${(job.salary_min || 0).toLocaleString()} - $${(job.salary_max || 0).toLocaleString()}</div>` : ''}
          </div>
          <div class="flex items-center gap-3 shrink-0 ml-4">
            ${job.url ? `<a href="${job.url}" target="_blank" class="text-blue-400 hover:underline font-semibold">Apply / View →</a>` : ''}
            <button onclick="deleteCustomJob(${idx})" class="text-slate-500 hover:text-red-400 p-1" title="Delete custom job">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `).join('');
      lucide.createIcons();
    }

    async function deleteCustomJob(idx) {
      if (!confirm('Remove this custom job?')) return;
      await fetch('/api/jobs/custom/' + idx, { method: 'DELETE' });
      showToast('Custom job removed');
      loadCustomJobs();
    }


    function setDryRunSubTab(sub) {
      if (sub === 'cards') {
        document.getElementById('dryRunCardsView').classList.remove('hidden');
        document.getElementById('dryRunEmailView').classList.add('hidden');
        document.getElementById('btnSubCards').className = 'bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
        document.getElementById('btnSubEmail').className = 'bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold';
      } else {
        document.getElementById('dryRunCardsView').classList.add('hidden');
        document.getElementById('dryRunEmailView').classList.remove('hidden');
        document.getElementById('btnSubCards').className = 'bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold';
        document.getElementById('btnSubEmail').className = 'bg-blue-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
      }
    }

    function renderAll() {
      if (!appConfig) return;
      // Roles
      const rolesList = document.getElementById('rolesList');
      rolesList.innerHTML = appConfig.profile.target_roles.map((r, i) => `
        <span class="bg-blue-950 border border-blue-800 text-blue-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          ${r} <button onclick="removeRole(${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Must
      document.getElementById('mustList').innerHTML = appConfig.filters.must_have_skills.map((s, i) => `
        <span class="bg-emerald-950 border border-emerald-800 text-emerald-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          ${s} <button onclick="removeSkill('must', ${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Nice
      document.getElementById('niceList').innerHTML = appConfig.filters.nice_to_have_skills.map((s, i) => `
        <span class="bg-amber-950 border border-amber-800 text-amber-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          ${s} <button onclick="removeSkill('nice', ${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Excluded
      document.getElementById('excludedList').innerHTML = appConfig.filters.excluded_terms.map((s, i) => `
        <span class="bg-red-950 border border-red-800 text-red-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          ${s} <button onclick="removeSkill('excluded', ${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Filters
      document.getElementById('candidateName').value = appConfig.profile.candidate_name;
      document.getElementById('expYears').value = appConfig.profile.experience_years;
      document.getElementById('expYearsVal').innerText = appConfig.profile.experience_years + ' Years';
      document.getElementById('salaryFloor').value = appConfig.profile.salary_floor_usd;

      // Locations
      document.getElementById('locationsList').innerHTML = appConfig.profile.preferred_locations.map((l, i) => `
        <span class="bg-emerald-950 border border-emerald-800 text-emerald-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          📍 ${l} <button onclick="removeLoc(${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Watchlist
      document.getElementById('watchlistGrid').innerHTML = appConfig.company_watchlist.map((w, i) => `
        <div class="bg-slate-950 border border-slate-800 p-2.5 rounded-lg flex justify-between items-center text-xs">
          <div>
            <div class="font-bold text-white">${w.name}</div>
            <div class="text-amber-400">${w.priority_multiplier}x Boost</div>
          </div>
          <button onclick="removeWatch(${i})" class="text-slate-500 hover:text-red-400">×</button>
        </div>
      `).join('');

      // Blacklist
      document.getElementById('blacklistGrid').innerHTML = appConfig.filters.excluded_companies.map((b, i) => `
        <span class="bg-red-950 border border-red-800 text-red-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
          ⛔ ${b} <button onclick="removeBlacklist(${i})" class="hover:text-red-400">×</button>
        </span>
      `).join('');

      // Sources
      document.getElementById('chkGreenhouse').checked = appConfig.sources.greenhouse.enabled;
      document.getElementById('greenhouseSlugs').value = (appConfig.sources.greenhouse.companies || []).join(', ');
      document.getElementById('chkLever').checked = appConfig.sources.lever.enabled;
      document.getElementById('leverSlugs').value = (appConfig.sources.lever.companies || []).join(', ');
      document.getElementById('chkAshby').checked = appConfig.sources.ashby.enabled;
      document.getElementById('ashbySlugs').value = (appConfig.sources.ashby.companies || []).join(', ');
      document.getElementById('chkRemotive').checked = appConfig.sources.remotive.enabled;
      document.getElementById('chkRemoteOK').checked = appConfig.sources.remoteok.enabled;
      document.getElementById('chkArbeitnow').checked = appConfig.sources.arbeitnow.enabled;
      document.getElementById('chkJobicy').checked = appConfig.sources.jobicy.enabled;
      document.getElementById('chkHN').checked = appConfig.sources.hackernews.enabled;

      if (appConfig.sources.twitter) {
        document.getElementById('chkTwitter').checked = appConfig.sources.twitter.enabled;
        document.getElementById('twitterQueries').value = (appConfig.sources.twitter.search_queries || []).join(', ');
        document.getElementById('twitterAccounts').value = (appConfig.sources.twitter.monitored_accounts || []).join(', ');
      }

      // Link Verification
      if (appConfig.link_verification) {
        document.getElementById('chkLinkVerify').checked = appConfig.link_verification.enabled;
        document.getElementById('verifyTimeout').value = appConfig.link_verification.timeout_seconds;
        document.getElementById('chkSoft404').checked = appConfig.link_verification.check_content_keywords;
      }

      // Schedule & Delivery
      document.getElementById('schedTz').value = appConfig.schedule.timezone;
      document.getElementById('schedTime').value = appConfig.schedule.daily_digest_time;
      document.getElementById('schedDay').value = appConfig.schedule.weekly_digest_day;
      document.getElementById('schedInstant').value = appConfig.schedule.instant_alert_threshold;
      document.getElementById('delivProvider').value = appConfig.delivery.email_provider;
      document.getElementById('delivEmail').value = appConfig.delivery.recipient_email;

      // Online Income Settings
      renderIncomeSettings();
    }

    function addRole() {
      const val = document.getElementById('inputRole').value.trim();
      if (!val) return;
      appConfig.profile.target_roles.push(val);
      document.getElementById('inputRole').value = '';
      renderAll();
    }
    function removeRole(i) { appConfig.profile.target_roles.splice(i, 1); renderAll(); }

    function addSkill(type) {
      const inp = type === 'must' ? 'inputMust' : type === 'nice' ? 'inputNice' : 'inputExcluded';
      const val = document.getElementById(inp).value.trim();
      if (!val) return;
      if (type === 'must') appConfig.filters.must_have_skills.push(val);
      if (type === 'nice') appConfig.filters.nice_to_have_skills.push(val);
      if (type === 'excluded') appConfig.filters.excluded_terms.push(val);
      document.getElementById(inp).value = '';
      renderAll();
    }
    function removeSkill(type, i) {
      if (type === 'must') appConfig.filters.must_have_skills.splice(i, 1);
      if (type === 'nice') appConfig.filters.nice_to_have_skills.splice(i, 1);
      if (type === 'excluded') appConfig.filters.excluded_terms.splice(i, 1);
      renderAll();
    }

    function addLocation() {
      const val = document.getElementById('inputLoc').value.trim();
      if (!val) return;
      appConfig.profile.preferred_locations.push(val);
      document.getElementById('inputLoc').value = '';
      renderAll();
    }
    function removeLoc(i) { appConfig.profile.preferred_locations.splice(i, 1); renderAll(); }

    function addWatchlist() {
      const name = document.getElementById('watchName').value.trim();
      const mult = parseFloat(document.getElementById('watchMult').value);
      if (!name) return;
      appConfig.company_watchlist.push({ name, priority_multiplier: mult });
      document.getElementById('watchName').value = '';
      renderAll();
    }
    function removeWatch(i) { appConfig.company_watchlist.splice(i, 1); renderAll(); }

    function addBlacklist() {
      const name = document.getElementById('blacklistName').value.trim();
      if (!name) return;
      appConfig.filters.excluded_companies.push(name);
      document.getElementById('blacklistName').value = '';
      renderAll();
    }
    function removeBlacklist(i) { appConfig.filters.excluded_companies.splice(i, 1); renderAll(); }

    async function saveConfig() {
      // Sync form fields back to appConfig
      appConfig.profile.candidate_name = document.getElementById('candidateName').value;
      appConfig.profile.experience_years = parseInt(document.getElementById('expYears').value);
      appConfig.profile.salary_floor_usd = parseFloat(document.getElementById('salaryFloor').value);

      appConfig.sources.greenhouse.enabled = document.getElementById('chkGreenhouse').checked;
      appConfig.sources.greenhouse.companies = document.getElementById('greenhouseSlugs').value.split(',').map(s => s.trim()).filter(Boolean);

      appConfig.sources.lever.enabled = document.getElementById('chkLever').checked;
      appConfig.sources.lever.companies = document.getElementById('leverSlugs').value.split(',').map(s => s.trim()).filter(Boolean);

      appConfig.sources.ashby.enabled = document.getElementById('chkAshby').checked;
      appConfig.sources.ashby.companies = document.getElementById('ashbySlugs').value.split(',').map(s => s.trim()).filter(Boolean);

      appConfig.sources.remotive.enabled = document.getElementById('chkRemotive').checked;
      appConfig.sources.remoteok.enabled = document.getElementById('chkRemoteOK').checked;
      appConfig.sources.arbeitnow.enabled = document.getElementById('chkArbeitnow').checked;
      appConfig.sources.jobicy.enabled = document.getElementById('chkJobicy').checked;
      appConfig.sources.hackernews.enabled = document.getElementById('chkHN').checked;

      if (!appConfig.sources.twitter) {
        appConfig.sources.twitter = { enabled: true, search_queries: [], monitored_accounts: [], max_tweets: 30 };
      }
      appConfig.sources.twitter.enabled = document.getElementById('chkTwitter').checked;
      appConfig.sources.twitter.search_queries = document.getElementById('twitterQueries').value.split(',').map(s => s.trim()).filter(Boolean);
      appConfig.sources.twitter.monitored_accounts = document.getElementById('twitterAccounts').value.split(',').map(s => s.trim()).filter(Boolean);

      if (!appConfig.link_verification) {
        appConfig.link_verification = { enabled: true, timeout_seconds: 6.0, max_concurrency: 20, check_content_keywords: true, cache_ttl_hours: 24 };
      }
      appConfig.link_verification.enabled = document.getElementById('chkLinkVerify').checked;
      appConfig.link_verification.timeout_seconds = parseFloat(document.getElementById('verifyTimeout').value) || 6.0;
      appConfig.link_verification.check_content_keywords = document.getElementById('chkSoft404').checked;

      appConfig.schedule.timezone = document.getElementById('schedTz').value;
      appConfig.schedule.daily_digest_time = document.getElementById('schedTime').value;
      appConfig.schedule.weekly_digest_day = document.getElementById('schedDay').value;
      appConfig.schedule.instant_alert_threshold = parseFloat(document.getElementById('schedInstant').value);

      appConfig.delivery.email_provider = document.getElementById('delivProvider').value;
      appConfig.delivery.recipient_email = document.getElementById('delivEmail').value;

      const res = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(appConfig)
      });
      if (res.ok) {
        showToast('Configuration saved successfully!');
      }
    }

    async function loadPresetProfile(name) {
      if (!name) return;
      const res = await fetch('/api/profiles/load', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ profile_name: name })
      });
      const data = await res.json();
      if (data.config) {
        appConfig = data.config;
        renderAll();
        showToast("Profile '" + name + "' activated!");
      }
    }

    async function triggerRun(dryRun) {
      const btn = document.getElementById('btnTestRun');
      btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5 animate-spin"></i> Running...';
      lucide.createIcons();
      try {
        const res = await fetch('/api/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dry_run: dryRun, force_all: true })
        });
        const data = await res.json();
        switchTab('dryrun');
        renderDryRunJobs(data.top_matches || []);
        showToast('Run completed! ' + (data.jobs_count || 0) + ' jobs processed.');
      } catch (e) {
        alert('Run error: ' + e);
      } finally {
        btn.innerHTML = '<i data-lucide="play" class="w-3.5 h-3.5 fill-white"></i> Test Run & Preview';
        lucide.createIcons();
      }
    }

    function renderDryRunJobs(jobs) {
      const container = document.getElementById('dryRunCardsView');
      if (!jobs || jobs.length === 0) {
        container.innerHTML = '<div class="bg-slate-900 p-8 rounded-xl text-center text-slate-500 text-xs">No jobs scored above threshold. Try expanding keywords or target companies.</div>';
        return;
      }
      container.innerHTML = jobs.map(item => `
        <div class="bg-slate-900 border border-slate-800 p-4 rounded-xl">
          <div class="flex justify-between items-start mb-2">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <h3 class="text-sm font-bold text-white">${item.job.title}</h3>
                ${item.job.is_verified ? `
                  <span class="bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
                    <i data-lucide="shield-check" class="w-3 h-3"></i> Verified Link
                  </span>
                ` : `
                  <span class="bg-red-950 text-red-400 border border-red-800 text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
                    <i data-lucide="alert-triangle" class="w-3 h-3"></i> ${item.job.verification_status || 'Unverified'}
                  </span>
                `}
              </div>
              <div class="text-xs text-blue-400 font-semibold">${item.job.company} • <span class="text-slate-400">${item.job.location}</span></div>
            </div>
            <span class="text-xs font-black px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
              ★ ${item.score}/10 Match
            </span>
          </div>
          <div class="bg-slate-950 p-2.5 rounded-lg border-l-2 border-blue-500 text-xs text-slate-300 my-2">
            <ul class="list-disc pl-4 space-y-0.5">
              ${(item.breakdown.highlights || []).map(h => `<li>${h}</li>`).join('')}
            </ul>
          </div>
          <div class="flex justify-between items-center pt-2 text-xs border-t border-slate-800">
            <span class="text-slate-500">Source: ${item.job.source}</span>
            <a href="${item.job.url}" target="_blank" class="bg-blue-600 hover:bg-blue-500 text-white font-bold px-3 py-1 rounded text-xs">Apply →</a>
          </div>
        </div>
      `).join('');
      lucide.createIcons();
    }


    async function loadTelemetry() {
      const res = await fetch('/api/logs');
      const data = await res.json();
      const logs = data.logs || [];
      const cont = document.getElementById('logsContainer');
      if (logs.length === 0) {
        cont.innerText = 'No past execution runs recorded.';
        return;
      }
      cont.innerHTML = `
        <div class="overflow-x-auto">
          <table class="w-full text-left">
            <thead class="bg-slate-950 text-slate-400">
              <tr>
                <th class="p-2">Run ID</th>
                <th class="p-2">Fetched</th>
                <th class="p-2">Instant (9.0+)</th>
                <th class="p-2">Digest (7.0+)</th>
                <th class="p-2">Duration</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-slate-800">
              ${logs.map(l => `
                <tr>
                  <td class="p-2 font-mono">${l.run_id}</td>
                  <td class="p-2 font-bold text-white">${l.total_fetched}</td>
                  <td class="p-2 text-emerald-400 font-bold">${l.instant_matches}</td>
                  <td class="p-2 text-cyan-400">${l.digest_matches}</td>
                  <td class="p-2 text-purple-300">${l.execution_time_seconds}s</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    async function clearCache() {
      if (confirm('Clear deduplication history?')) {
        await fetch('/api/seen-jobs/clear', { method: 'POST' });
        showToast('Seen cache cleared!');
      }
    }

    let currentIncomeCategory = '';

    function setIncomeSubTab(sub) {
      document.getElementById('incomeCardsView').classList.add('hidden');
      document.getElementById('incomeEmailView').classList.add('hidden');
      document.getElementById('incomeSettingsView').classList.add('hidden');
      document.getElementById('incomeCustomView').classList.add('hidden');

      ['Cards', 'Email', 'Settings', 'Custom'].forEach(t => {
        document.getElementById('btnIncomeSub' + t).className = 'bg-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-semibold';
      });

      if (sub === 'cards') {
        document.getElementById('incomeCardsView').classList.remove('hidden');
        document.getElementById('btnIncomeSubCards').className = 'bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
      } else if (sub === 'email') {
        document.getElementById('incomeEmailView').classList.remove('hidden');
        document.getElementById('btnIncomeSubEmail').className = 'bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
        document.getElementById('incomeEmailIframe').src = '/api/income/preview-email?t=' + Date.now();
      } else if (sub === 'settings') {
        document.getElementById('incomeSettingsView').classList.remove('hidden');
        document.getElementById('btnIncomeSubSettings').className = 'bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
      } else if (sub === 'custom') {
        document.getElementById('incomeCustomView').classList.remove('hidden');
        document.getElementById('btnIncomeSubCustom').className = 'bg-emerald-600 text-white px-3 py-1.5 rounded-lg text-xs font-semibold';
        loadCustomIncomeList();
      }
      lucide.createIcons();
    }

    function renderIncomeSettings() {
      if (!appConfig || !appConfig.online_income) return;
      const inc = appConfig.online_income;
      const list = document.getElementById('incomeCountriesList');
      if (list) {
        list.innerHTML = (inc.eligible_countries || []).map((c, i) => `
          <span class="bg-emerald-950 border border-emerald-800 text-emerald-200 text-xs px-2.5 py-1 rounded-md flex items-center gap-1.5">
            🌍 ${c} <button onclick="removeIncomeCountry(${i})" class="hover:text-red-400">×</button>
          </span>
        `).join('');
      }

      document.getElementById('incomeMinRate').value = inc.minimum_hourly_rate_usd || 5.0;
      document.getElementById('incomeMaxHours').value = inc.maximum_hours_per_week || 25;
      document.getElementById('chkIncomeLinkVerify').checked = inc.require_link_verification !== false;

      if (inc.sources) {
        document.getElementById('chkIncomeAiEval').checked = inc.sources.ai_evaluation?.enabled !== false;
        document.getElementById('chkIncomeUserTesting').checked = inc.sources.user_testing?.enabled !== false;
        document.getElementById('chkIncomeAcademic').checked = inc.sources.academic_tutoring?.enabled !== false;
        document.getElementById('chkIncomeSupport').checked = inc.sources.transcription_support?.enabled !== false;
      }
    }

    function addIncomeCountry() {
      const val = document.getElementById('incomeInputCountry').value.trim();
      if (!val) return;
      if (!appConfig.online_income.eligible_countries) appConfig.online_income.eligible_countries = [];
      appConfig.online_income.eligible_countries.push(val);
      document.getElementById('incomeInputCountry').value = '';
      renderIncomeSettings();
    }

    function removeIncomeCountry(i) {
      appConfig.online_income.eligible_countries.splice(i, 1);
      renderIncomeSettings();
    }

    async function saveIncomeConfig() {
      if (!appConfig.online_income) appConfig.online_income = {};
      appConfig.online_income.minimum_hourly_rate_usd = parseFloat(document.getElementById('incomeMinRate').value) || 5.0;
      appConfig.online_income.maximum_hours_per_week = parseInt(document.getElementById('incomeMaxHours').value) || 25;
      appConfig.online_income.require_link_verification = document.getElementById('chkIncomeLinkVerify').checked;

      if (!appConfig.online_income.sources) appConfig.online_income.sources = {};
      appConfig.online_income.sources.ai_evaluation = { enabled: document.getElementById('chkIncomeAiEval').checked };
      appConfig.online_income.sources.user_testing = { enabled: document.getElementById('chkIncomeUserTesting').checked };
      appConfig.online_income.sources.academic_tutoring = { enabled: document.getElementById('chkIncomeAcademic').checked };
      appConfig.online_income.sources.transcription_support = { enabled: document.getElementById('chkIncomeSupport').checked };

      const res = await fetch('/api/income/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(appConfig.online_income)
      });
      if (res.ok) {
        showToast('Online Income preferences saved!');
      }
    }

    async function triggerIncomeRun(dryRun) {
      const btn = document.getElementById('btnScanIncome');
      btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5 animate-spin"></i> Scanning...';
      lucide.createIcons();
      try {
        const res = await fetch('/api/income/run', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ dry_run: dryRun, force_all: true })
        });
        const data = await res.json();
        setIncomeSubTab('cards');
        renderIncomeOpportunities(data.top_matches || []);
        showToast('Found ' + (data.opportunities_count || 0) + ' income opportunities!');
      } catch (e) {
        alert('Income scan error: ' + e);
      } finally {
        btn.innerHTML = '<i data-lucide="refresh-cw" class="w-3.5 h-3.5"></i> Scan Online Income';
        lucide.createIcons();
      }
    }

    async function loadIncomeOpportunities(category) {
      const catParam = category !== undefined ? category : currentIncomeCategory;
      const minQuality = document.getElementById('selIncomeMinQuality') ? document.getElementById('selIncomeMinQuality').value : '7.0';
      const minSideJob = document.getElementById('selIncomeSideJobFit') ? document.getElementById('selIncomeSideJobFit').value : '0.0';
      const trustTier = document.getElementById('selIncomeTrustTier') ? document.getElementById('selIncomeTrustTier').value : '';
      const showRejected = document.getElementById('chkShowRejectedIncome') ? document.getElementById('chkShowRejectedIncome').checked : false;

      let url = '/api/income/opportunities?min_quality=' + minQuality + '&min_side_job_fit=' + minSideJob;
      if (catParam) url += '&category=' + encodeURIComponent(catParam);
      if (trustTier) url += '&source_trust_tier=' + encodeURIComponent(trustTier);
      if (showRejected) url += '&include_rejected=true';

      const res = await fetch(url);
      const data = await res.json();
      if (!data.opportunities || data.opportunities.length === 0) {
        if (!showRejected && minQuality === '7.0' && !catParam) {
          triggerIncomeRun(true);
        } else {
          renderIncomeOpportunities([]);
        }
      } else {
        renderIncomeOpportunities(data.opportunities);
      }
    }

    function filterIncomeCategory(cat) {
      currentIncomeCategory = cat;
      document.querySelectorAll('.income-cat-pill').forEach(btn => {
        btn.className = 'income-cat-pill bg-slate-900 border border-slate-800 text-slate-400 hover:text-white px-3 py-1 rounded-full';
      });
      event.target.className = 'income-cat-pill bg-emerald-950 border border-emerald-700 text-emerald-300 px-3 py-1 rounded-full font-semibold';
      loadIncomeOpportunities(cat);
    }

    function renderIncomeOpportunities(opps) {
      const container = document.getElementById('incomeCardsView');
      if (!opps || opps.length === 0) {
        container.innerHTML = '<div class="bg-slate-900 p-8 rounded-xl text-center text-slate-500 text-xs">No opportunities found for the selected quality/category criteria. Click "Scan Online Income" to run discovery.</div>';
        return;
      }
      container.innerHTML = opps.map(item => {
        const isDiscarded = item.action === 'discard' || item.score === 0;
        const qScore = item.breakdown.quality_score || item.opportunity.quality_score || 0;
        const sScore = item.breakdown.side_job_fit_score || item.opportunity.side_job_fit_score || 0;
        const trustTier = (item.opportunity.source_trust_tier || 'tier_1_highest').replace('_', ' ').toUpperCase();
        const rejections = item.breakdown.rejection_reasons || item.opportunity.rejection_reasons || [];

        return `
        <div class="bg-slate-900 border ${isDiscarded ? 'border-red-900/60 opacity-75' : 'border-slate-800'} p-4 rounded-xl">
          <div class="flex justify-between items-start mb-2">
            <div>
              <div class="flex items-center gap-2 mb-1">
                <h3 class="text-sm font-bold text-white">${item.opportunity.title}</h3>
                <span class="bg-emerald-950 text-emerald-400 border border-emerald-800 text-[10px] font-bold px-1.5 py-0.5 rounded flex items-center gap-1">
                  <i data-lucide="award" class="w-3 h-3"></i> ${trustTier}
                </span>
                ${isDiscarded ? `<span class="bg-red-950 text-red-400 border border-red-800 text-[10px] font-bold px-1.5 py-0.5 rounded">GATED OUT</span>` : ''}
              </div>
              <div class="text-xs text-emerald-400 font-semibold">${item.opportunity.organization} • <span class="text-slate-400">📍 ${item.opportunity.location_eligibility}</span></div>
            </div>
            <div class="flex flex-col items-end gap-1">
              <div class="flex items-center gap-2">
                <span class="text-xs font-black px-2.5 py-1 rounded ${item.score >= 9 ? 'bg-emerald-950 text-emerald-300 border border-emerald-800' : 'bg-blue-950 text-blue-300 border border-blue-800'}">
                  ★ ${item.score}/10 Overall
                </span>
                <button onclick="dismissIncomeOpportunity('${item.opportunity.fingerprint}')" class="text-slate-500 hover:text-red-400 p-1" title="Dismiss opportunity">
                  <i data-lucide="x" class="w-3.5 h-3.5"></i>
                </button>
              </div>
              <div class="text-[11px] font-semibold text-slate-400">
                Quality: <span class="text-emerald-400 font-bold">${qScore}/10</span> • Side-Job: <span class="text-indigo-400 font-bold">${sScore}/10</span>
              </div>
            </div>
          </div>

          <!-- Metadata Chips -->
          <div class="flex flex-wrap gap-1.5 my-2">
            ${item.opportunity.pay_rate_display ? `<span class="bg-amber-950/80 border border-amber-800 text-amber-300 text-[11px] font-mono px-2 py-0.5 rounded font-bold">💵 ${item.opportunity.pay_rate_display}</span>` : '<span class="bg-slate-950 border border-slate-800 text-slate-400 text-[11px] px-2 py-0.5 rounded">💵 Flexible / Task Pay</span>'}
            <span class="bg-slate-950 border border-slate-800 text-slate-300 text-[11px] px-2 py-0.5 rounded">📂 ${(item.opportunity.category || '').replace('_', ' ')}</span>
            <span class="bg-slate-950 border border-slate-800 text-indigo-300 text-[11px] px-2 py-0.5 rounded">🌙 ${item.opportunity.is_asynchronous ? '100% Asynchronous' : 'Flexible Hours'}</span>
          </div>

          <p class="text-xs text-slate-300 mb-2">${item.opportunity.description || ''}</p>

          ${isDiscarded && rejections.length > 0 ? `
          <div class="bg-red-950/40 p-2.5 rounded-lg border-l-2 border-red-500 text-xs text-red-200 my-2">
            <div class="font-bold text-red-400 text-[11px] uppercase mb-1">Reason Blocked by Quality Gate:</div>
            <ul class="list-disc pl-4 space-y-0.5">
              ${rejections.map(r => `<li>${r}</li>`).join('')}
            </ul>
          </div>` : ''}

          ${!isDiscarded ? `
          <div class="bg-slate-950 p-2.5 rounded-lg border-l-2 border-emerald-500 text-xs text-slate-300 my-2">
            <div class="font-bold text-emerald-400 text-[11px] uppercase mb-1">Why this is worth considering:</div>
            <ul class="list-disc pl-4 space-y-0.5">
              ${(item.breakdown.highlights || []).map(h => `<li>${h}</li>`).join('')}
            </ul>
          </div>` : ''}

          <div class="flex justify-between items-center pt-2 text-xs border-t border-slate-800">
            <span class="text-slate-500">Source: ${(item.opportunity.source || '').replace('_', ' ')}</span>
            <a href="${item.opportunity.application_url || item.opportunity.url}" target="_blank" class="bg-emerald-600 hover:bg-emerald-500 text-white font-bold px-3 py-1 rounded text-xs flex items-center gap-1">
              Apply / Start Earning →
            </a>
          </div>
        </div>
      `}).join('');
      lucide.createIcons();
    }

    async function dismissIncomeOpportunity(fingerprint) {
      if (!confirm('Dismiss this opportunity? It will not appear in future alerts.')) return;
      await fetch('/api/income/dismiss', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ fingerprint })
      });
      showToast('Opportunity dismissed');
      loadIncomeOpportunities();
    }

    async function submitCustomIncome() {
      const title = document.getElementById('customIncTitle').value.trim();
      const organization = document.getElementById('customIncOrg').value.trim();
      const category = document.getElementById('customIncCat').value;
      const pay_rate_display = document.getElementById('customIncPayDisplay').value.trim();
      const url = document.getElementById('customIncUrl').value.trim();
      const location_eligibility = document.getElementById('customIncLocation').value.trim() || 'Worldwide';
      const description = document.getElementById('customIncDesc').value.trim();

      if (!title || !organization) {
        alert('Please provide at least Title and Platform/Organization.');
        return;
      }

      const res = await fetch('/api/income/custom', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, organization, category, pay_rate_display, url, location_eligibility, description })
      });
      if (res.ok) {
        showToast('Custom income gig added!');
        document.getElementById('customIncTitle').value = '';
        document.getElementById('customIncOrg').value = '';
        document.getElementById('customIncPayDisplay').value = '';
        document.getElementById('customIncUrl').value = '';
        document.getElementById('customIncDesc').value = '';
        loadCustomIncomeList();
      }
    }

    async function loadCustomIncomeList() {
      const res = await fetch('/api/income/custom');
      const data = await res.json();
      const list = data.custom_opportunities || [];
      const cont = document.getElementById('customIncomeList');
      if (!cont) return;
      if (!list || list.length === 0) {
        cont.innerHTML = '<div class="text-xs text-slate-500">No custom income opportunities entered yet. Add one above!</div>';
        return;
      }
      cont.innerHTML = list.map((opp, idx) => `
        <div class="bg-slate-950 border border-slate-800 p-3 rounded-lg flex justify-between items-start text-xs">
          <div>
            <div class="font-bold text-white text-sm">${opp.title}</div>
            <div class="text-emerald-400 font-semibold mt-0.5">${opp.organization} • <span class="text-slate-400">${opp.location_eligibility}</span></div>
            ${opp.pay_rate_display ? `<div class="text-amber-400 font-mono font-semibold mt-1">💵 ${opp.pay_rate_display}</div>` : ''}
            ${opp.description ? `<p class="text-slate-400 mt-1 line-clamp-2">${opp.description}</p>` : ''}
          </div>
          <div class="flex items-center gap-3 shrink-0 ml-4">
            ${opp.url ? `<a href="${opp.url}" target="_blank" class="text-blue-400 hover:underline font-semibold">Apply →</a>` : ''}
            <button onclick="deleteCustomIncome(${idx})" class="text-slate-500 hover:text-red-400 p-1" title="Delete opportunity">
              <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
            </button>
          </div>
        </div>
      `).join('');
      lucide.createIcons();
    }

    async function deleteCustomIncome(idx) {
      if (!confirm('Remove this custom income opportunity?')) return;
      await fetch('/api/income/custom/' + idx, { method: 'DELETE' });
      showToast('Custom opportunity removed');
      loadCustomIncomeList();
    }

    function showToast(msg) {
      const t = document.getElementById('toast');
      document.getElementById('toastMsg').innerText = msg;
      t.classList.remove('hidden');
      setTimeout(() => t.classList.add('hidden'), 3000);
    }

    window.onload = init;
  </script>
</body>
</html>
"""
