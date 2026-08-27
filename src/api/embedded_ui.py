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
      ['roles', 'filters', 'watchlist', 'sources', 'schedule', 'custom', 'dryrun', 'health'].forEach(t => {
        document.getElementById('tab-' + t).classList.add('hidden');
        document.getElementById('tabBtn-' + t).className = 'flex items-center gap-2 px-3.5 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-900 transition';
      });
      document.getElementById('tab-' + tabId).classList.remove('hidden');
      document.getElementById('tabBtn-' + tabId).className = 'flex items-center gap-2 px-3.5 py-2 rounded-lg bg-blue-600 text-white transition';
      if (tabId === 'health') loadTelemetry();
      if (tabId === 'custom') loadCustomJobs();
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

      // Schedule & Delivery
      document.getElementById('schedTz').value = appConfig.schedule.timezone;
      document.getElementById('schedTime').value = appConfig.schedule.daily_digest_time;
      document.getElementById('schedDay').value = appConfig.schedule.weekly_digest_day;
      document.getElementById('schedInstant').value = appConfig.schedule.instant_alert_threshold;
      document.getElementById('delivProvider').value = appConfig.delivery.email_provider;
      document.getElementById('delivEmail').value = appConfig.delivery.recipient_email;
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
              <h3 class="text-sm font-bold text-white">${item.job.title}</h3>
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
