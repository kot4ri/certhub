      const main = document.getElementById("main"),
        esc = (v) =>
          String(v ?? "").replace(
            /[&<>"']/g,
            (c) =>
              ({
                "&": "&amp;",
                "<": "&lt;",
                ">": "&gt;",
                '"': "&quot;",
                "'": "&#39;",
              })[c],
          ),
        localTime = (v) => {
          if (!v) return "-";
          const d = new Date(v);
          return Number.isNaN(d.getTime())
            ? String(v)
            : new Intl.DateTimeFormat(undefined, {
                year: "numeric",
                month: "2-digit",
                day: "2-digit",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
                hour12: false,
              }).format(d);
        };
      let floatingTooltip = null,
        floatingTooltipOwner = null;
      const hideFloatingTooltip = () => {
        if (floatingTooltip) floatingTooltip.remove();
        floatingTooltip = null;
        floatingTooltipOwner = null;
      };
      const showFloatingTooltip = (owner) => {
        const message = owner && owner.dataset.tip;
        if (!message || floatingTooltipOwner === owner) return;
        hideFloatingTooltip();
        const tip = document.createElement("div");
        tip.className = "floating-tooltip";
        tip.textContent = message;
        tip.style.visibility = "hidden";
        document.body.appendChild(tip);
        const anchor = owner.getBoundingClientRect(),
          bounds = tip.getBoundingClientRect(),
          left = Math.max(
            10,
            Math.min(anchor.left, window.innerWidth - bounds.width - 10),
          );
        let top = anchor.top - bounds.height - 8;
        if (top < 8) top = anchor.bottom + 8;
        tip.style.left = left + "px";
        tip.style.top = top + "px";
        tip.style.visibility = "visible";
        floatingTooltip = tip;
        floatingTooltipOwner = owner;
      };
      document.addEventListener("mouseover", (event) => {
        const owner = event.target.closest?.(".hover-detail");
        if (owner) showFloatingTooltip(owner);
      });
      document.addEventListener("mouseout", (event) => {
        const owner = event.target.closest?.(".hover-detail");
        if (owner && !owner.contains(event.relatedTarget)) hideFloatingTooltip();
      });
      document.addEventListener("focusin", (event) => {
        const owner = event.target.closest?.(".hover-detail");
        if (owner) showFloatingTooltip(owner);
      });
      document.addEventListener("focusout", (event) => {
        if (event.target.closest?.(".hover-detail")) hideFloatingTooltip();
      });
      document.addEventListener("scroll", hideFloatingTooltip, true);
      window.addEventListener("resize", hideFloatingTooltip);
      const app = document.querySelector(".app"),
        navToggle = document.querySelector(".nav-toggle");
      if (localStorage.getItem("certhub-nav-collapsed") === "1")
        app.classList.add("nav-collapsed");
      const updateNavToggle = () => {
        const collapsed = app.classList.contains("nav-collapsed");
        navToggle.title = collapsed ? "展开侧边栏" : "收起侧边栏";
        navToggle.setAttribute("aria-label", navToggle.title);
        navToggle.setAttribute("aria-expanded", String(!collapsed));
      };
      navToggle.onclick = () => {
        app.classList.toggle("nav-collapsed");
        localStorage.setItem(
          "certhub-nav-collapsed",
          app.classList.contains("nav-collapsed") ? "1" : "0",
        );
        updateNavToggle();
      };
      updateNavToggle();
      let onboardingLocked = false;
      const tableObserver = new MutationObserver(() => {
        main.querySelectorAll("table").forEach((table) => {
          if (table.parentElement && table.parentElement.classList.contains("table-shell")) return;
          const shell = document.createElement("div");
          shell.className = "table-shell";
          table.parentNode.insertBefore(shell, table);
          shell.appendChild(table);
        });
      });
      tableObserver.observe(main, { childList: true, subtree: true });
      const versionStyle = document.createElement("style");
      versionStyle.textContent =
        '.version-dot{position:relative;display:inline-block;width:8px;height:8px;margin-left:6px;border-radius:50%;background:#f56c6c;vertical-align:1px;cursor:pointer}.version-dot:hover:after,.version-dot:focus:after{content:attr(data-tip);position:absolute;z-index:50;left:50%;bottom:calc(100% + 9px);transform:translateX(-50%);padding:7px 10px;border-radius:4px;background:#303133;color:#fff;font-size:12px;font-weight:400;line-height:1.4;white-space:nowrap;box-shadow:0 3px 10px #0003}.version-dot:hover:before,.version-dot:focus:before{content:"";position:absolute;z-index:51;left:50%;bottom:calc(100% + 4px);transform:translateX(-50%);border:5px solid transparent;border-top-color:#303133}';
      document.head.appendChild(versionStyle);
      function osBadge(r) {
        const name = String(r.os_name || ""),
          version = String(r.os_version || ""),
          text = (name + " " + version).toLowerCase();
        let label, icon;
        if (text.includes("windows")) {
          const match = version.match(/windows[-\s]+(\d+)/i);
          label = "Windows" + (match ? " " + match[1] : "");
          icon =
            '<svg viewBox="0 0 16 16"><path fill="#168BDB" d="M1 2.2 7 1.4v6H1zm7-1L15 0v7.4H8zM1 8.6h6v6L1 13.8zm7 0h7V16l-7-1.2z"/></svg>';
        } else if (text.includes("almalinux")) {
          label = version.replace(/\s*\([^)]*\)\s*$/, "") || "AlmaLinux";
          icon =
            '<svg viewBox="0 0 100 100" aria-label="AlmaLinux"><path fill="#86DA2F" d="M86 55.9c3.6-.3 6.5 2.1 6.8 5.7.3 3.8-2.4 6.8-6 7.1-3.5.3-6.5-2.4-6.8-5.8-.3-3.8 2.2-6.6 6-7z"/><path fill="#24C2FF" d="M42.1 85.5c0-3.6 2.8-6.4 6.1-6.4s6.5 3.1 6.5 6.5c0 3.3-2.8 6.3-6 6.4-4 0-6.6-2.5-6.6-6.5zM53.6 50.6c.4-.4.7-.3 1.1 0 9.2 5.6 13.9 16.5 9.7 27.2-1.1 2.8-4.7 5.6-7.4 4.9-1.1-.3-1.7-.8-2.2-1.5-1.3-1.7-2.6-3.2-4.7-3.9-2.2-.7-4.2-.3-6.1.8-1.7 1-3.3 2.2-5.4 1-1.3-.7-3.3-5-2.9-6.4.3-.6.8-.6 1.4-.6 3.5-.6 6.3-2.2 8.9-4.4.8-.7 1.5-.7 2.2.3 1.1 1.7 2.5 3.1 4.3 4 3.6 2.1 7.1.3 7.5-3.9.4-3.5-.8-6.5-1.9-9.6-1.3-2.8-2.8-5.4-4.5-7.9z"/><path fill="#FFCB12" d="M51.9 44.9c-.6.3-.8-.1-1-.6-5.1-9.6-3.6-21.7 5.4-28.9 2.4-1.9 6.8-2.4 8.8-.4.8.7 1 1.5 1.1 2.5.3 2.1.7 4.2 2.1 5.8 1.5 1.8 3.5 2.5 5.7 2.4 1.9 0 3.9-.3 5.1 1.9.7 1.3.4 6.1-.7 7.1-.6.4-1 .1-1.4 0-3.2-1.3-6.5-1.3-9.9-.7-1.1.1-1.7-.1-1.7-1.4-.1-2.1-.6-4-1.7-5.8-2.1-3.8-6-3.9-8.5-.4-2.1 2.8-2.6 6.1-3.2 9.4-.4 3-.2 6.1-.1 9.1zM73.3 11.8c3.5-.3 6.8 2.5 7.1 6 .3 3.3-2.5 6.5-5.8 6.8-3.6.3-6.8-2.4-7.1-5.8-.3-3.5 2.2-6.7 5.8-7z"/><path fill="#0069DA" d="M49.1 51.4c-.6 2.8-1.8 5.4-3.5 7.8-5 7.5-12.2 10.6-21.1 9.7-3.2-.3-5.8-2.9-6.1-5.6-.1-1.1.1-1.9.8-2.8 1-1.3 1.8-2.4 2.2-3.9.8-3.1-.3-5.6-2.5-7.8-3.1-3.1-2.6-5.8 1-8.1.4-.3 1-.6 1.5-.8.8-.4 1.5-.4 1.8.6 1.3 3.2 3.8 5.6 6.5 7.5 1 .8 1 1.4.1 2.4-1.7 1.8-2.6 4-2.8 6.5-.3 3.1 1.5 5 4.6 5 1.9 0 3.8-.7 5.4-1.5 4.3-2.2 7.6-5.4 10.8-8.8.6 0 .8-.3 1.3-.2zM15 61.3c-3.3.4-6.7-2.4-6.9-5.8-.3-3.3 2.5-6.7 5.7-6.9 3.6-.4 6.9 2.1 7.2 5.4.1 3.1-2 7-6 7.3z"/><path fill="#FF4649" d="M26.3 22.3c.3 0 1 .1 1.7.3 5.1 1 8.3-.8 10-5.7 1.1-3.2 3.5-4.2 6.5-2.5.1 0 .1.1.3.1 3.1 1.8 3.1 2.1 1 4.9-1.7 2.2-2.5 4.7-2.9 7.4-.3 1.5-.8 1.8-2.2 1.3-2.2-.8-4.6-.8-6.9 0-2.6.8-3.8 3.2-2.9 5.8 1.1 3.5 4.2 5 6.8 6.8s5.7 2.8 8.6 4c.4.1 1.1.1 1 .8-.1.4-.7.4-1.3.4-6.3.3-12.2-.7-17.1-4.9-4.6-3.8-7.9-8.3-7.4-14.7.7-2.1 2.2-3.6 4.8-4zM37 14.5c.4 3.6-2.1 6.7-5.8 7.2-3.2.4-6.5-2.2-6.9-5.3-.4-4 1.8-6.9 5.6-7.4 3.4-.4 6.7 2.3 7.1 5.5z"/><path fill="#86DA2F" d="M55.4 47c-.3-.4-.1-.8.3-1.1 7.9-7.2 19.7-8.6 28.9-1.5 2.4 1.9 3.9 6 2.6 8.3-.6 1-1.3 1.4-2.1 1.7-1.9.8-3.8 1.7-5 3.5-1.3 1.8-1.5 3.9-1 6.1.4 1.8 1.1 3.8-.7 5.4-1 1-5.7 1.8-6.9 1-.6-.4-.4-.8-.3-1.4.4-3.5-.4-6.7-1.7-9.7-.4-1.1-.3-1.7.8-1.9 1.9-.6 3.8-1.5 5.1-2.9 3.1-2.9 2.4-6.7-1.7-8.3-3.2-1.4-6.5-1.1-9.7-.8-2.9-.1-5.8.8-8.6 1.6z"/></svg>';
        } else if (text.includes("rocky")) {
          label = version.replace(/\s*\([^)]*\)\s*$/, "") || "Rocky Linux";
          icon =
            '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="#10B981"/><path fill="#fff" d="M3 11.5 7.2 4l1.5 2.4L10 5l3 6.5H9.8L7.2 7.2 4.8 11.5z"/></svg>';
        } else if (text.includes("ubuntu")) {
          label = version.replace(/\s*\([^)]*\)\s*$/, "") || "Ubuntu";
          icon =
            '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.5" fill="none" stroke="#E95420" stroke-width="2"/><circle cx="8" cy="2" r="1.5" fill="#E95420"/><circle cx="3" cy="11" r="1.5" fill="#E95420"/><circle cx="13" cy="11" r="1.5" fill="#E95420"/></svg>';
        } else if (text.includes("debian")) {
          label = version.replace(/\s*\([^)]*\)\s*$/, "") || "Debian";
          icon =
            '<svg viewBox="0 0 16 16"><circle cx="8" cy="8" r="7" fill="#A80030"/><path fill="none" stroke="#fff" stroke-width="1.4" stroke-linecap="round" d="M11.5 6.2c-.7-2.5-5.2-2.4-6.4.2-1.1 2.3 1.2 4.8 3.8 4.2 1.8-.4 2.6-2.1 1.8-3.3-.7-1-2.6-.8-2.8.4"/></svg>';
        } else {
          label = (version || name || "-").replace(/^linux\s*/i, "Linux ");
          icon =
            '<svg viewBox="0 0 16 16"><ellipse cx="8" cy="9" rx="5" ry="6" fill="#252525"/><ellipse cx="8" cy="10" rx="3.2" ry="4" fill="#f5f5f5"/><circle cx="6.3" cy="5.8" r=".8" fill="#fff"/><circle cx="9.7" cy="5.8" r=".8" fill="#fff"/><circle cx="6.4" cy="5.9" r=".35"/><circle cx="9.6" cy="5.9" r=".35"/><path fill="#F5A623" d="m8 7 1.5 1L8 8.8 6.5 8zM3 14l3-1-.8 2H3zm10 0-3-1 .8 2H13z"/></svg>';
        }
        return (
          '<span style="display:inline-flex;align-items:center;gap:5px"><span style="display:inline-flex;width:14px;height:14px">' +
          icon +
          "</span>" +
          esc(label.trim()) +
          "</span>"
        );
      }
      const api = (method, data = {}) =>
        fetch(
          "/certhub-api?action=admin_call&method=" + encodeURIComponent(method),
          {
            method: "POST",
            credentials: "same-origin",
            headers: {
              "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            },
            body: new URLSearchParams(data),
          },
        ).then(async (r) => {
          if (r.status === 401) throw Error("登录已失效，请重新登录宝塔面板");
          const x = await r.json();
          if (!x.status) throw Error(x.msg || "请求失败");
          return x.data;
        });
      const fail = (e) =>
        (main.innerHTML = '<p class="bad">' + esc(e.message || e) + "</p>");
      const uiIcon = (name) => {
        const icons = {
          certificate: '<svg viewBox="0 0 24 24"><path d="M7 3h10v18l-5-3-5 3z"/><path d="m9.5 10.5 1.7 1.7 3.5-3.7"/></svg>',
          server: '<svg viewBox="0 0 24 24"><rect x="3" y="4" width="18" height="6" rx="2"/><rect x="3" y="14" width="18" height="6" rx="2"/><path d="M7 7h.01M7 17h.01M11 10v4"/></svg>',
          online: '<svg viewBox="0 0 24 24"><path d="M3 12h4l2-6 4 12 2-6h6"/></svg>',
          sync: '<svg viewBox="0 0 24 24"><path d="M20 7h-5V2"/><path d="M20 7a8 8 0 0 0-14-1.5L4 8"/><path d="M4 17h5v5"/><path d="M4 17a8 8 0 0 0 14 1.5l2-2.5"/></svg>',
          download: '<svg viewBox="0 0 24 24"><path d="M12 3v12m-4-4 4 4 4-4"/><path d="M4 19h16"/></svg>',
          userAdd: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="4"/><path d="M3 21c0-4 2.5-7 6-7 2 0 3.6.8 4.7 2M18 10v6m-3-3h6"/></svg>',
        };
        return icons[name] || icons.certificate;
      };
      function copyText(value, field) {
        let area = field,
          temporary = false;
        if (!area) {
          area = document.createElement("textarea");
          area.value = value;
          area.setAttribute("readonly", "");
          area.style.cssText = "position:fixed;left:-9999px;top:0;opacity:0";
          document.body.appendChild(area);
          temporary = true;
        }
        area.focus();
        area.select();
        area.setSelectionRange(0, area.value.length);
        try {
          if (document.execCommand("copy")) {
            if (temporary) area.remove();
            return Promise.resolve();
          }
        } catch (_) {}
        if (temporary) area.remove();
        return navigator.clipboard && window.isSecureContext
          ? navigator.clipboard.writeText(value)
          : Promise.reject(new Error("浏览器禁止访问剪贴板"));
      }
      function modal(title, html) {
        const m = document.createElement("div");
        m.className = "mask";
        m.innerHTML =
          '<section class="modal"><header class="head"><h3>' +
          esc(title) +
          '</h3><button class="close">&times;</button></header><div class="body">' +
          html +
          "</div></section>";
        document.body.appendChild(m);
        m.querySelector(".close").onclick = () => m.remove();
        m.onclick = (e) => {
          if (e.target === m) m.remove();
        };
        return m;
      }
      async function dashboard() {
        try {
          const [d, certRows, eventData] = await Promise.all([
              api("dashboard"),
              api("certificates"),
              api("pull_events", { page: "1" }),
            ]),
            certs = Array.isArray(certRows) ? certRows : certRows.items || [],
            events = Array.isArray(eventData) ? eventData.slice(0, 5) : (eventData.items || []).slice(0, 5),
            now = Date.now();
          let healthy = 0, expiring = 0, expired = 0;
          certs.forEach((c) => {
            const ts = new Date(c.not_after || "").getTime();
            if (!Number.isFinite(ts)) return;
            const days = (ts - now) / 86400000;
            if (days < 0) expired += 1;
            else if (days <= 30) expiring += 1;
            else healthy += 1;
          });
          const known = healthy + expiring + expired,
            healthPct = known ? Math.round((healthy / known) * 100) : 100,
            unknown = Math.max(0, certs.length - known),
            metric = (label, value, icon, color, soft) =>
              '<div class="card metric-card" style="--metric:' + color + ';--metric-soft:' + soft + '"><div class="metric-label">' + label + '</div><div class="metric-line"><div class="number" style="color:' + color + '">' + esc(value) + '</div><span class="metric-icon">' + icon + '</span></div></div>',
            activities = events.length
              ? events.map((r) => '<div class="activity-row"><span class="activity-icon">' + uiIcon(String(r.action || "").includes("update") ? "sync" : "download") + '</span><div class="activity-copy"><b>' + esc(r.client_name || "未知客户端") + '</b><span>' + esc((r.certificate_name || "配置同步") + " · " + (r.ip_address || "未知 IP")) + '</span></div><time class="activity-time">' + esc(localTime(r.created_at)) + '</time></div>').join("")
              : '<div class="muted" style="padding:28px 0;text-align:center">暂无拉取活动</div>';
          main.innerHTML =
            '<header class="dash-head"><div><h1>概览</h1><p>集中查看证书、客户端与同步服务的运行状态</p></div><span class="muted"><i class="status-pulse"></i>服务运行正常</span></header>' +
            '<section class="cards">' +
              metric("纳管证书", d.certificates, uiIcon("certificate"), "#0b9b6b", "#e7f8f2") +
              metric("有效客户端", d.clients, uiIcon("server"), "#3978f6", "#ebf1ff") +
              metric("24 小时在线", d.online_24h, uiIcon("online"), "#0797a6", "#e6f7f8") +
              metric("24 小时拉取", d.pulls_24h, uiIcon("sync"), "#7057dc", "#f0edff") +
            '</section><section class="dash-grid"><div class="panel dash-panel"><div class="panel-title"><h3>证书健康状态</h3><span class="muted">共 ' + esc(certs.length) + ' 张</span></div><div class="health-layout"><div class="health-ring" style="--pct:' + healthPct + '"><div class="health-center"><strong>' + healthPct + '%</strong><span>健康证书</span></div></div><div><div class="health-row"><i class="health-dot" style="--dot:#12a875"></i><span>有效（超过 30 天）</span><b>' + healthy + '</b></div><div class="health-row"><i class="health-dot" style="--dot:#f59e0b"></i><span>即将过期（30 天内）</span><b>' + expiring + '</b></div><div class="health-row"><i class="health-dot" style="--dot:#e55757"></i><span>已过期</span><b>' + expired + '</b></div>' + (unknown ? '<div class="health-row"><i class="health-dot" style="--dot:#a6afbd"></i><span>日期未知</span><b>' + unknown + '</b></div>' : '') + '</div></div></div><div class="panel dash-panel"><div class="panel-title"><h3>最近活动</h3><button class="btn dash-nav" data-target="events" style="background:#eef4ff;color:#3978f6;box-shadow:none">查看全部</button></div>' + activities + '</div></section>' +
            '<section class="dash-bottom"><div class="panel dash-panel"><div class="panel-title"><h3>快捷操作</h3></div><div class="quick-actions"><a class="quick-action dash-nav" data-target="certificates"><i>' + uiIcon("certificate") + '</i><span><b>管理证书</b><br><small class="muted">查看、检查和管理证书</small></span></a><a class="quick-action dash-nav" data-target="clients"><i>' + uiIcon("userAdd") + '</i><span><b>新增客户端</b><br><small class="muted">注册新的下发服务</small></span></a></div></div><div class="panel dash-panel"><div class="panel-title"><h3>API 信息</h3><span class="good"><i class="status-pulse"></i>可用</span></div><div class="api-url">' + esc((d.panel_base_url || "尚未设置") + d.api_path) + '</div><p class="muted" style="margin:13px 0 0">客户端定期同步配置，仅在证书发生变化时执行替换。</p></div></section>';
          main.querySelectorAll(".dash-nav").forEach((item) => item.onclick = () => {
            const button = document.querySelector('.nav button[data-page="' + item.dataset.target + '"]');
            if (button) button.click();
          });
        } catch (e) {
          fail(e);
        }
      }
      function tablePager(className, page, total) {
        if (total <= 1) return "";
        const style =
            "min-width:34px;height:34px;padding:0 9px;border:1px solid #dcdfe6;border-radius:3px;cursor:pointer;",
          items = paginationItems(page, total);
        return (
          '<nav class="' +
          className +
          '" style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:18px"><button style="' +
          style +
          '" data-page="' +
          (page - 1) +
          '" ' +
          (page <= 1 ? "disabled" : "") +
          ">‹</button>" +
          items
            .map((x) =>
              x === "…"
                ? '<span style="padding:0 3px;color:#909399">…</span>'
                : '<button style="' +
                  style +
                  (x === page
                    ? "border-color:#20a53a;background:#20a53a;color:#fff;"
                    : "background:#fff;color:#606266;") +
                  '" data-page="' +
                  x +
                  '">' +
                  x +
                  "</button>",
            )
            .join("") +
          '<button style="' +
          style +
          '" data-page="' +
          (page + 1) +
          '" ' +
          (page >= total ? "disabled" : "") +
          ">›</button></nav>"
        );
      }
      async function local(pageArg = 1) {
        try {
          const rows = await api("discover_local"),
            pages = Math.max(1, Math.ceil(rows.length / 10)),
            page = Math.min(pages, Math.max(1, Number(pageArg) || 1)),
            pageRows = rows.slice((page - 1) * 10, page * 10);
          main.innerHTML =
            '<div class="toolbar client-toolbar"><div class="client-heading"><h2>本地证书</h2><p>扫描宝塔面板证书目录，共 ' +
            rows.length +
            ' 条</p></div></div><div class="client-batch-bar"><button class="btn" id="scan">重新扫描</button></div><table><tr><th>名称</th><th>路径</th><th>域名</th><th>品牌/类型</th><th>有效期</th><th>状态</th><th>操作</th></tr>' +
            pageRows
              .map(
                (r, i) =>
                  "<tr><td>" +
                  esc(r.name) +
                  "</td><td>" +
                  esc(r.path) +
                  "</td><td>" +
                  esc((r.sans || []).join(", ")) +
                  "</td><td><b>" +
                  esc(r.issuer_brand || "未知") +
                  '</b><br><span class="muted">' +
                  esc(r.validation_type || "未知") +
                  '</span></td><td><span class="muted">起</span> ' +
                  esc(localTime(r.not_before)) +
                  '<br><span class="muted">止</span> ' +
                  esc(localTime(r.not_after)) +
                  '</td><td class="' +
                  (r.error ? "bad" : "good") +
                  '">' +
                  esc(r.error || "有效") +
                  "</td><td>" +
                  (r.managed
                    ? "已纳管"
                    : '<button class="btn manage" data-i="' +
                      i +
                      '">纳管</button>') +
                  "</td></tr>",
              )
              .join("") +
            "</table>" +
            tablePager("local-pagination", page, pages);
          document.getElementById("scan").onclick = () => local(page);
          main
            .querySelectorAll(".local-pagination button:not(:disabled)")
            .forEach((b) => (b.onclick = () => local(Number(b.dataset.page))));
          main.querySelectorAll(".manage").forEach(
            (b) =>
              (b.onclick = () => {
                const r = pageRows[Number(b.dataset.i)];
                api("import_local", { path: r.path, name: r.name })
                  .then(() => local(page))
                  .catch(fail);
              }),
          );
        } catch (e) {
          fail(e);
        }
      }
      async function certificates(pageArg = 1) {
        try {
          const rows = await api("certificates"),
            pages = Math.max(1, Math.ceil(rows.length / 10)),
            page = Math.min(pages, Math.max(1, Number(pageArg) || 1)),
            pageRows = rows.slice((page - 1) * 10, page * 10);
          main.innerHTML =
            '<div class="toolbar client-toolbar"><div class="client-heading"><h2>纳管证书</h2><p>查看并维护已纳管证书，共 ' +
            rows.length +
            ' 条</p></div></div><div class="client-batch-bar"><button class="btn" id="check">检查全部</button></div><table><tr><th>名称</th><th>主题/SAN</th><th>来源</th><th>品牌/类型</th><th>有效期</th><th>状态</th><th>操作</th></tr>' +
            pageRows
              .map(
                (r) =>
                  "<tr><td>" +
                  esc(r.name) +
                  "</td><td>" +
                  esc(r.subject_name) +
                  '<br><span class="muted">' +
                  esc((r.sans || []).join(", ")) +
                  "</span></td><td>" +
                  esc(r.source_path) +
                  "</td><td><b>" +
                  esc(r.issuer_brand || "未知") +
                  '</b><br><span class="muted">' +
                  esc(r.validation_type || "未知") +
                  '</span></td><td><span class="muted">起</span> ' +
                  esc(localTime(r.not_before)) +
                  '<br><span class="muted">止</span> ' +
                  esc(localTime(r.not_after)) +
                  "</td><td>" +
                  esc(r.last_error || "正常") +
                  '</td><td><button class="btn danger remove" data-id="' +
                  r.id +
                  '">取消纳管</button></td></tr>',
              )
              .join("") +
            "</table>" +
            tablePager("certificate-pagination", page, pages);
          document.getElementById("check").onclick = () =>
            api("sync_now").then(() => certificates(page));
          main
            .querySelectorAll(".certificate-pagination button:not(:disabled)")
            .forEach(
              (b) => (b.onclick = () => certificates(Number(b.dataset.page))),
            );
          main
            .querySelectorAll(".remove")
            .forEach(
              (b) =>
                (b.onclick = () =>
                  confirm("仅取消纳管，不删除源证书。继续？") &&
                  api("remove_certificate", { id: b.dataset.id }).then(() =>
                    certificates(page),
                  )),
            );
        } catch (e) {
          fail(e);
        }
      }
      function clientForm(c, certs, edit) {
        const chosen = new Set((c.certificate_ids || []).map(Number));
        return (
          '<div class="row"><label>客户端名称</label><input type="text" class="name" value="' +
          esc(c.name || "") +
          '"></div><div class="row"><label>平台</label><select class="platform" ' +
          (edit ? "disabled" : "") +
          '><option value="linux" ' +
          ((c.platform || "linux") === "linux" ? "selected" : "") +
          '>Linux</option><option value="windows" ' +
          (c.platform === "windows" ? "selected" : "") +
          '>Windows</option></select></div><div class="row"><label>允许使用的证书（可多选）</label><div class="checks">' +
          certs
            .map(
              (x) =>
                '<label><input type="checkbox" class="cert" value="' +
                x.id +
                '" ' +
                (chosen.has(Number(x.id)) ? "checked" : "") +
                "> " +
                esc(x.name) +
                "</label>",
            )
            .join("") +
          '</div></div><div class="row"><label class="check-label"><input type="checkbox" class="limit" ' +
          (c.allowed_ip ? "checked" : "") +
          '> 限制请求来源（IP 或域名）</label><input type="text" class="ip" value="' +
          esc(c.allowed_ip || "") +
          '" placeholder="IPv4、IPv6 或域名"><p class="muted">填写域名时，每次请求都会解析 A/AAAA 记录，任意地址与实际来源一致即放行。</p></div><div class="row"><label>证书部署方式</label><select class="mode"><option value="files-only">服务托管证书目录</option><option value="custom" ' +
          (c.deploy_mode === "custom" ? "selected" : "") +
          '>自定义下载目录</option><option value="bt-panel" ' +
          (c.deploy_mode === "bt-panel" ? "selected" : "") +
          '>客户端宝塔面板标准路径</option></select></div><div class="row path-row"><label>自定义下载根目录</label><input type="text" class="path" value="' +
          esc(c.download_path || "") +
          '" placeholder="/etc/certhub/certificates"></div><div class="row bt-row"><label class="check-label"><input type="checkbox" class="sites" ' +
          (c.auto_deploy_sites ? "checked" : "") +
          '> 更新使用完全相同证书的网站</label><p class="muted">仅当网站当前证书的主体和完整 SAN 集合完全一致时替换。</p></div><div class="row"><label>证书同步计划（crontab 五段格式）</label><input type="text" class="schedule" value="' +
          esc(c.sync_schedule || "0 * * * *") +
          '" placeholder="0 * * * *"><p class="muted">例如：每小时 <code>0 * * * *</code>，每天 03:30 <code>30 3 * * *</code>。Agent 每 5 分钟同步配置。</p></div><div class="actions"><button class="btn save">' +
          (edit ? "保存配置" : "创建并生成安装命令") +
          '</button></div><div class="result"></div>'
        );
      }
      function bindClient(m, c, edit, onCreated) {
        const mode = m.querySelector(".mode"),
          platform = m.querySelector(".platform"),
          limit = m.querySelector(".limit"),
          btOption = mode.querySelector('option[value="bt-panel"]'),
          filesOption = mode.querySelector('option[value="files-only"]'),
          homeOption = new Option(
            "用户目录\\CertHub\\certificates",
            "user-home",
          );
        mode.add(homeOption, 0);
        const refresh = () => {
          const windows = platform.value === "windows";
          btOption.hidden = windows;
          filesOption.hidden = windows;
          homeOption.hidden = !windows;
          if (windows && ["bt-panel", "files-only"].includes(mode.value))
            mode.value = "user-home";
          if (!windows && mode.value === "user-home") mode.value = "files-only";
          m.querySelector(".ip").style.display = limit.checked
            ? "block"
            : "none";
          m.querySelector(".path-row").style.display =
            mode.value === "custom" ? "block" : "none";
          m.querySelector(".bt-row").style.display =
            !windows && mode.value === "bt-panel" ? "block" : "none";
        };
        if (c.deploy_mode === "user-home") mode.value = "user-home";
        mode.onchange = platform.onchange = limit.onchange = refresh;
        refresh();
        m.querySelector(".save").onclick = (e) => {
          const data = {
            name: m.querySelector(".name").value,
            platform: platform.value,
            panel_base_url: location.origin,
            certificate_ids: JSON.stringify(
              [...m.querySelectorAll(".cert:checked")].map((x) =>
                Number(x.value),
              ),
            ),
            allowed_ip: limit.checked ? m.querySelector(".ip").value : "",
            deploy_mode: mode.value,
            download_path: m.querySelector(".path").value,
            auto_deploy_sites:
              !btOption.hidden && m.querySelector(".sites").checked ? "1" : "0",
            sync_schedule: m.querySelector(".schedule").value,
          };
          if (edit) data.id = c.id;
          e.currentTarget.disabled = true;
          api(edit ? "update_client" : "create_client", data)
            .then((d) => {
              if (edit) {
                m.remove();
                clients();
              } else if (onCreated) onCreated(d);
              else {
                m.querySelector(".head h3").textContent = "安装命令";
                const body = m.querySelector(".body");
                body.innerHTML = '<div class="result"></div>';
                command(body.querySelector(".result"), d);
              }
            })
            .catch((x) => {
              e.currentTarget.disabled = false;
              alert(x.message || x);
            });
        };
      }
      function command(box, d) {
        const windows = d.platform === "windows";
        box.innerHTML =
          '<div class="toolbar"><b>' +
          (windows ? "Windows 一键安装命令" : "安装命令") +
          '</b><button class="btn copy">复制命令</button></div><pre class="command">' +
          esc(d.install_command) +
          '</pre><p class="muted">' +
          (windows
            ? "请在 PowerShell 中粘贴运行；命令会自动下载、申请管理员权限并安装计划任务。"
            : "请在终端中粘贴运行。") +
          '</p><p class="note">只能使用一次，30 分钟后失效。</p>';
        box.querySelector(".copy").onclick = (e) =>
          copyText(d.install_command)
            .then(() => (e.currentTarget.textContent = "已复制"))
            .catch(() => alert("复制失败，请手动选择命令"));
      }
      async function clients(pageArg = 1) {
        try {
          const [rows, certs, defaults] = await Promise.all([
              api("clients"),
              api("certificates"),
              api("dashboard"),
            ]),
            names = new Map(certs.map((c) => [Number(c.id), c.name]));
          const behavior = (r) => {
            const selected = (r.certificate_ids || []).map(
                (id) => names.get(Number(id)) || "#" + id,
              ),
              certNames = selected.join("、"),
              certText = selected.length === 1 ? selected[0] : selected.length > 1 ? selected.length + " 个证书" : "未授权",
              certDisplay = selected.length > 1
                ? '<span class="hover-detail" tabindex="0" data-tip="' + esc(certNames) + '">' + esc(certText) + "</span>"
                : esc(certText);
            let destination;
            if (r.platform === "windows")
              destination =
                r.deploy_mode === "custom"
                  ? r.download_path || "自定义目录"
                  : "用户目录\\CertHub\\certificates";
            else if (r.deploy_mode === "bt-panel")
              destination =
                "宝塔标准证书夹" +
                (r.auto_deploy_sites ? " · 自动更新网站" : "");
            else if (r.deploy_mode === "custom")
              destination = r.download_path || "自定义目录";
            else destination = "服务托管证书目录";
            return (
              '<div class="cell-lines"><span><b>证书</b> ' +
              certDisplay +
              '</span><span class="ellipsis muted" title="' +
              esc(destination) +
              '">' +
              esc(destination) +
              '</span><span class="muted">' +
              esc(r.sync_schedule || "0 * * * *") +
              " · " +
              esc(r.allowed_ip || "不限来源") +
              "</span></div>"
            );
          };
          const forceStatus = (r) =>
              r.force_sync_token
                ? '<span class="note" title="' +
                  esc(localTime(r.force_sync_requested_at)) +
                  '">等待执行</span>'
                : r.force_sync_completed_at
                  ? '<span class="good" title="' +
                    esc(localTime(r.force_sync_completed_at)) +
                    '">已执行</span>'
                  : "未下发",
            updateStatus = (r) =>
              r.update_token
                ? '<span class="note" title="' +
                  esc(localTime(r.update_requested_at)) +
                  '">等待更新</span>'
                : r.update_completed_at
                  ? '<span class="good" title="' +
                    esc(localTime(r.update_completed_at)) +
                    '">已更新 ' +
                    esc(r.agent_version || r.update_completed_version || "-") +
                    "</span>"
                  : "未下发",
            cleanupStatus = (r) =>
              r.cleanup_token
                ? '<span class="note" title="' +
                  esc(localTime(r.cleanup_requested_at)) +
                  '">等待清理</span>'
                : r.cleanup_completed_at
                  ? '<span class="good" title="' +
                    esc(localTime(r.cleanup_completed_at)) +
                    '">已清理</span>'
                  : "未下发";
          const managedRows = rows.filter((r) => r.status !== "revoked"),
            revokedRows = rows.filter((r) => r.status === "revoked"),
            clientPages = Math.max(1, Math.ceil(managedRows.length / 10)),
            clientPage = Math.min(
              clientPages,
              Math.max(1, Number(pageArg) || 1),
            ),
            pageRows = managedRows.slice(
              (clientPage - 1) * 10,
              clientPage * 10,
            );
          const managedHtml = pageRows
            .map((r) => {
              const lastIp = String(r.last_ip || "-"),
                shortenedIp = lastIp.includes(":") && lastIp.length > 20,
                ipDisplay = shortenedIp
                  ? '<span class="hover-detail" tabindex="0" data-tip="' + esc(lastIp) + '">' + esc(lastIp.slice(0, 20)) + "</span>"
                  : esc(lastIp),
                outdated =
                  r.status === "active" &&
                  r.agent_version &&
                  r.latest_agent_version &&
                  r.agent_version !== r.latest_agent_version,
                dot = outdated
                  ? '<span class="version-dot" data-id="' +
                    r.id +
                    '" tabindex="0" data-tip="当前 ' +
                    esc(r.agent_version) +
                    "，最新 " +
                    esc(r.latest_agent_version) +
                    '" aria-label="当前 ' +
                    esc(r.agent_version) +
                    "，最新 " +
                    esc(r.latest_agent_version) +
                    '"></span>'
                  : "";
              return (
                '<tr><td><input type="checkbox" class="client-select" value="' +
                r.id +
                '" ' +
                (r.status === "active" ? "" : "disabled") +
                "></td><td><b>" +
                esc(r.name) +
                '</b><br><span class="muted ellipsis" style="max-width:150px" title="' +
                esc(r.client_uuid) +
                '">' +
                esc(r.client_uuid) +
                "</span></td><td>" +
                behavior(r) +
                '</td><td><div class="task-chips"><span class="task-chip"><b>拉取</b>' +
                forceStatus(r) +
                '</span><span class="task-chip"><b>更新</b>' +
                updateStatus(r) +
                '</span><span class="task-chip"><b>清理</b>' +
                cleanupStatus(r) +
                '</span></div></td><td><div class="cell-lines"><span class="ellipsis" title="' +
                esc(r.hostname || "-") +
                '">' +
                esc(r.hostname || "-") +
                '</span><span style="display:flex;align-items:center;gap:6px;white-space:nowrap">' +
                osBadge(r) +
                '<span class="muted">·</span><b>Agent ' +
                esc(r.agent_version || "-") +
                "</b>" +
                dot +
                '</span></div></td><td><div class="cell-lines"><span>' +
                ipDisplay +
                '</span><span class="muted">' +
                esc(localTime(r.last_seen_at)) +
                "</span></div></td><td>" +
                esc(r.status) +
                "</td><td>" +
                (r.status === "pending"
                  ? '<button class="btn enroll" data-id="' +
                    r.id +
                    '">安装命令</button> '
                  : "") +
                '<button class="btn edit" data-id="' +
                r.id +
                '">编辑</button> <button class="btn danger revoke" data-id="' +
                r.id +
                '">撤权</button> <button class="btn danger delete" data-id="' +
                r.id +
                '">删除</button></td></tr>'
              );
            })
            .join("");
          const pageButtonStyle =
              "min-width:34px;height:34px;padding:0 9px;border:1px solid #dcdfe6;border-radius:3px;cursor:pointer;",
            clientPageItems = paginationItems(clientPage, clientPages),
            clientPager =
              clientPages > 1
                ? '<nav class="client-pagination" style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:18px"><button style="' +
                  pageButtonStyle +
                  '" data-page="' +
                  (clientPage - 1) +
                  '" ' +
                  (clientPage <= 1 ? "disabled" : "") +
                  ">‹</button>" +
                  clientPageItems
                    .map((x) =>
                      x === "…"
                        ? '<span style="padding:0 3px;color:#909399">…</span>'
                        : '<button style="' +
                          pageButtonStyle +
                          (x === clientPage
                            ? "border-color:#20a53a;background:#20a53a;color:#fff;"
                            : "background:#fff;color:#606266;") +
                          '" data-page="' +
                          x +
                          '">' +
                          x +
                          "</button>",
                    )
                    .join("") +
                  '<button style="' +
                  pageButtonStyle +
                  '" data-page="' +
                  (clientPage + 1) +
                  '" ' +
                  (clientPage >= clientPages ? "disabled" : "") +
                  ">›</button></nav>"
                : "";
          main.innerHTML =
            '<div class="toolbar client-toolbar"><div class="client-heading"><h2>客户端管理</h2><p>管理客户端权限、同步任务与 Agent 更新</p></div></div><div class="client-batch-bar"><div class="action-menu" id="clientActionMenu"><button class="btn btn-secondary action-menu-trigger" id="clientMore" type="button">批量操作 <svg viewBox="0 0 16 16"><path d="m4 6 4 4 4-4"/></svg></button><div class="action-menu-popover" style="left:0;right:auto"><button id="forceSync" type="button"><span>立即拉取证书</span></button><button id="updateClients" type="button"><span>更新选中客户端</span></button></div></div><button class="btn" id="add">新增客户端</button><button class="btn btn-secondary" id="revokedClients">已撤销列表（' +
            revokedRows.length +
            '）</button></div><table class="client-table"><tr><th><input type="checkbox" id="selectAll" aria-label="全选"></th><th>客户端</th><th>配置</th><th>任务状态</th><th>系统信息/版本</th><th>最后在线</th><th>状态</th><th>操作</th></tr>' +
            managedHtml +
            "</table>" +
            clientPager;
          const selectable = [
              ...main.querySelectorAll(".client-select:not(:disabled)"),
            ],
            selected = () =>
              selectable.filter((x) => x.checked).map((x) => Number(x.value));
          const actionMenu = document.getElementById("clientActionMenu");
          document.getElementById("clientMore").onclick = (e) => {
            e.stopPropagation();
            actionMenu.classList.toggle("open");
            if (actionMenu.classList.contains("open"))
              setTimeout(
                () =>
                  document.addEventListener(
                    "click",
                    () => actionMenu.classList.remove("open"),
                    { once: true },
                  ),
                0,
              );
          };
          actionMenu.querySelector(".action-menu-popover").onclick = (e) =>
            e.stopPropagation();
          document.getElementById("selectAll").onchange = (e) =>
            selectable.forEach((x) => (x.checked = e.currentTarget.checked));
          document.getElementById("forceSync").onclick = () => {
            const ids = selected();
            if (!ids.length) return alert("请先选择服务器");
            if (
              confirm(
                "让选中的服务器在下次配置同步时立即重新下载并部署全部授权证书？",
              )
            )
              api("force_sync_clients", { client_ids: JSON.stringify(ids) })
                .then(clients)
                .catch(fail);
          };
          document.getElementById("updateClients").onclick = () => {
            const ids = selected();
            if (!ids.length) return alert("请先选择客户端");
            if (confirm("向选中的客户端下发最新版本更新指令？"))
              api("update_clients", { client_ids: JSON.stringify(ids) })
                .then(clients)
                .catch(fail);
          };
          main.querySelectorAll(".version-dot").forEach(
            (dot) =>
              (dot.onclick = () => {
                const c = rows.find((x) => String(x.id) === dot.dataset.id),
                  shell =
                    c.platform === "windows" ? "管理员 PowerShell" : "终端",
                  m = modal(
                    "更新客户端",
                    "<p>是否将客户端 <b>" +
                      esc(c.name) +
                      "</b> 从 <b>" +
                      esc(c.agent_version) +
                      "</b> 更新到 <b>" +
                      esc(c.latest_agent_version) +
                      '</b>？</p><p class="muted">客户端将在下一次配置同步时下载、校验并安装更新。</p><div class="row"><label>手动更新命令</label><textarea id="manualUpdateCommand" class="command" readonly style="display:block;width:100%;min-height:150px;resize:vertical;border:0">' +
                      esc(c.manual_update_command || "暂未生成可用命令") +
                      '</textarea><p class="muted">复制失败时可点击文本框，然后按 Ctrl+C 手动复制。</p></div><div class="actions"><button class="btn" id="manualClientUpdate">复制手动更新命令</button><button class="btn" id="confirmClientUpdate">确认自动更新</button></div><p id="manualUpdateHint" class="good" style="display:none"></p>',
                  );
                const field = m.querySelector("#manualUpdateCommand");
                m.querySelector("#manualClientUpdate").onclick = (e) =>
                  copyText(c.manual_update_command, field)
                    .then(() => {
                      e.currentTarget.textContent = "已复制命令";
                      const hint = m.querySelector("#manualUpdateHint");
                      hint.style.display = "block";
                      hint.className = "good";
                      hint.textContent =
                        "命令已复制，请在客户端的" + shell + "中执行。";
                    })
                    .catch(() => {
                      field.focus();
                      field.select();
                      const hint = m.querySelector("#manualUpdateHint");
                      hint.style.display = "block";
                      hint.className = "note";
                      hint.textContent =
                        "浏览器禁止自动复制，命令已全选，请按 Ctrl+C 后在客户端的" +
                        shell +
                        "中执行。";
                    });
                m.querySelector("#confirmClientUpdate").onclick = (e) => {
                  e.currentTarget.disabled = true;
                  api("update_clients", { client_ids: JSON.stringify([c.id]) })
                    .then(() => {
                      m.remove();
                      clients();
                    })
                    .catch((x) => {
                      e.currentTarget.disabled = false;
                      alert(x.message || x);
                    });
                };
              }),
          );
          main
            .querySelectorAll(".client-pagination button:not(:disabled)")
            .forEach(
              (b) => (b.onclick = () => clients(Number(b.dataset.page))),
            );
          document.getElementById("revokedClients").onclick = () => {
            const m = modal(
                "已撤销客户端 (" + revokedRows.length + ")",
                '<div id="revokedList"></div>',
              ),
              renderRevoked = (requested = 1) => {
                const pages = Math.max(1, Math.ceil(revokedRows.length / 10)),
                  page = Math.min(pages, Math.max(1, requested)),
                  items = revokedRows.slice((page - 1) * 10, page * 10),
                  target = m.querySelector("#revokedList"),
                  numbers = paginationItems(page, pages);
                target.innerHTML = items.length
                  ? items
                      .map(
                        (r) =>
                          '<div style="padding:12px 0;border-bottom:1px solid #ebeef5"><div style="display:grid;grid-template-columns:minmax(0,1fr) auto;align-items:center;gap:12px"><div><b>' +
                          esc(r.name) +
                          '</b> <span class="muted">' +
                          esc(r.client_uuid) +
                          '</span><br><span class="muted">' +
                          osBadge(r) +
                          " · Agent " +
                          esc(r.agent_version || "-") +
                          " · 最后在线 " +
                          esc(localTime(r.last_seen_at)) +
                          '</span></div><div><button class="btn modal-restore" data-id="' +
                          r.id +
                          '">恢复</button> <button class="btn danger modal-delete" data-id="' +
                          r.id +
                          '">删除</button></div></div><details style="margin-top:8px"><summary class="muted" style="cursor:pointer">查看原配置</summary><div style="padding:8px 0 0 14px">' +
                          behavior(r) +
                          "</div></details></div>",
                      )
                      .join("")
                  : '<p class="muted">暂无已撤销客户端</p>';
                if (pages > 1)
                  target.innerHTML +=
                    '<nav class="revoked-pagination" style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:16px"><button style="' +
                    pageButtonStyle +
                    '" data-page="' +
                    (page - 1) +
                    '" ' +
                    (page <= 1 ? "disabled" : "") +
                    ">‹</button>" +
                    numbers
                      .map((x) =>
                        x === "…"
                          ? '<span style="padding:0 3px;color:#909399">…</span>'
                          : '<button style="' +
                            pageButtonStyle +
                            (x === page
                              ? "border-color:#20a53a;background:#20a53a;color:#fff;"
                              : "background:#fff;color:#606266;") +
                            '" data-page="' +
                            x +
                            '">' +
                            x +
                            "</button>",
                      )
                      .join("") +
                    '<button style="' +
                    pageButtonStyle +
                    '" data-page="' +
                    (page + 1) +
                    '" ' +
                    (page >= pages ? "disabled" : "") +
                    ">›</button></nav>";
                target
                  .querySelectorAll(".revoked-pagination button:not(:disabled)")
                  .forEach(
                    (b) =>
                      (b.onclick = () => renderRevoked(Number(b.dataset.page))),
                  );
                target.querySelectorAll(".modal-restore").forEach(
                  (b) =>
                    (b.onclick = () =>
                      confirm(
                        "恢复后需要在原客户端重新执行安装命令，原证书授权和配置会保留。继续？",
                      ) &&
                      api("restore_client", { id: b.dataset.id })
                        .then((d) => {
                          m.remove();
                          const installModal = modal(
                            "恢复客户端",
                            '<p class="note">旧认证凭据已失效，请在原客户端重新执行以下命令。</p><div class="result"></div>',
                          );
                          command(installModal.querySelector(".result"), d);
                        })
                        .catch((x) => alert(x.message || x))),
                );
                target.querySelectorAll(".modal-delete").forEach(
                  (b) =>
                    (b.onclick = () =>
                      confirm("确定彻底删除？此操作不可恢复。") &&
                      api("delete_client", { id: b.dataset.id })
                        .then(() => {
                          const index = revokedRows.findIndex(
                            (r) => String(r.id) === b.dataset.id,
                          );
                          if (index >= 0) revokedRows.splice(index, 1);
                          m.querySelector(".head h3").textContent =
                            "已撤销客户端 (" + revokedRows.length + ")";
                          document.getElementById(
                            "revokedClients",
                          ).textContent = "已撤销 (" + revokedRows.length + ")";
                          renderRevoked(page);
                        })
                        .catch((x) => alert(x.message || x))),
                );
              };
            renderRevoked();
          };
          document.getElementById("add").onclick = () => {
            const initial = {
                sync_schedule: defaults.default_sync_schedule || "0 * * * *",
              },
              m = modal("新增客户端", clientForm(initial, certs, false));
            bindClient(m, initial, false);
          };
          main.querySelectorAll(".edit").forEach(
            (b) =>
              (b.onclick = () => {
                const c = rows.find((x) => String(x.id) === b.dataset.id),
                  m = modal("编辑客户端配置", clientForm(c, certs, true));
                bindClient(m, c, true);
              }),
          );
          main.querySelectorAll(".enroll").forEach(
            (b) =>
              (b.onclick = () =>
                api("reissue_enrollment", { id: b.dataset.id }).then((d) => {
                  const m = modal("安装命令", '<div class="result"></div>');
                  command(m.querySelector(".result"), d);
                })),
          );
          main.querySelectorAll(".restore").forEach(
            (b) =>
              (b.onclick = () =>
                confirm(
                  "恢复后需要在原客户端重新执行安装命令，原证书授权和配置会保留。继续？",
                ) &&
                api("restore_client", { id: b.dataset.id })
                  .then((d) => {
                    const m = modal(
                      "恢复客户端",
                      '<p class="note">旧认证凭据已失效，请在原客户端重新执行以下命令。</p><div class="result"></div>',
                    );
                    command(m.querySelector(".result"), d);
                    clients();
                  })
                  .catch((x) => alert(x.message || x))),
          );
          main.querySelectorAll(".revoke").forEach(
            (b) =>
              (b.onclick = () => {
                const c = rows.find((x) => String(x.id) === b.dataset.id),
                  m = modal(
                    "撤销客户端权限",
                    "<p>确定撤销客户端 <b>" +
                      esc(c.name) +
                      '</b> 的全部访问权限？</p><label class="check-label"><input type="checkbox" id="cleanupCerts">要求客户端 Agent 清空由 CertHub 保存的证书</label><p class="note">如果客户端已离线、失控或 Agent 无法运行，清理可能无法成功；勾选后服务端会等待清理回报再正式撤销。</p><div class="actions"><button class="btn danger" id="confirmRevoke">确认撤销</button></div>',
                  );
                m.querySelector("#confirmRevoke").onclick = () =>
                  api("revoke_client", {
                    id: c.id,
                    cleanup_certificates: m.querySelector("#cleanupCerts")
                      .checked
                      ? "1"
                      : "0",
                  })
                    .then(() => {
                      m.remove();
                      clients();
                    })
                    .catch((x) => alert(x.message || x));
              }),
          );
          main
            .querySelectorAll(".delete")
            .forEach(
              (b) =>
                (b.onclick = () =>
                  confirm("确定彻底删除？此操作不可恢复。") &&
                  api("delete_client", { id: b.dataset.id }).then(clients)),
            );
        } catch (e) {
          fail(e);
        }
      }
      function paginationItems(current, total) {
        if (total <= 10) return Array.from({ length: total }, (_, i) => i + 1);
        const start = Math.max(2, Math.min(current - 3, total - 8)),
          items = [1];
        if (start > 2) items.push("…");
        items.push(...Array.from({ length: 8 }, (_, i) => start + i));
        if (start + 7 < total - 1) items.push("…");
        items.push(total);
        return items;
      }
      async function events(page = 1) {
        try {
          const d = await api("pull_events", { page: String(page) }),
            rows = d.items || [],
            pages = paginationItems(d.page, d.pages),
            buttonStyle =
              "min-width:34px;height:34px;padding:0 9px;border:1px solid #dcdfe6;border-radius:3px;cursor:pointer;";
          main.innerHTML =
            '<div class="toolbar"><h2>日志</h2><span class="muted">共 ' +
            d.total +
            " 条，每页 10 条</span></div><table><tr><th>时间</th><th>客户端</th><th>动作/证书</th><th>来源 IP</th><th>系统/版本</th></tr>" +
            rows
              .map(
                (r) =>
                  "<tr><td>" +
                  esc(localTime(r.created_at)) +
                  "</td><td>" +
                  esc(r.client_name) +
                  "</td><td>" +
                  esc(r.action) +
                  " / " +
                  esc(r.certificate_name || "-") +
                  "</td><td>" +
                  esc(r.ip_address || "-") +
                  '</td><td><div class="cell-lines"><span>' +
                  esc(r.hostname || "-") +
                  '</span><span style="display:flex;align-items:center;gap:6px;white-space:nowrap">' +
                  osBadge(r) +
                  '<span class="muted">·</span><b>Agent ' +
                  esc(r.agent_version || "-") +
                  "</b></span></div></td></tr>",
              )
              .join("") +
            '</table><nav class="pagination" style="display:flex;align-items:center;justify-content:center;gap:6px;margin-top:18px"><button style="' +
            buttonStyle +
            '" data-page="' +
            (d.page - 1) +
            '" ' +
            (d.page <= 1 ? "disabled" : "") +
            ">‹</button>" +
            pages
              .map((x) =>
                x === "…"
                  ? '<span style="padding:0 3px;color:#909399">…</span>'
                  : '<button style="' +
                    buttonStyle +
                    (x === d.page
                      ? "border-color:#20a53a;background:#20a53a;color:#fff;"
                      : "background:#fff;color:#606266;") +
                    '" data-page="' +
                    x +
                    '">' +
                    x +
                    "</button>",
              )
              .join("") +
            '<button style="' +
            buttonStyle +
            '" data-page="' +
            (d.page + 1) +
            '" ' +
            (d.page >= d.pages ? "disabled" : "") +
            ">›</button></nav>";
          main
            .querySelectorAll(".pagination button:not(:disabled)")
            .forEach((b) => (b.onclick = () => events(Number(b.dataset.page))));
        } catch (e) {
          fail(e);
        }
      }
      async function settings() {
        try {
          const d = await api("dashboard");
          main.innerHTML =
            '<div class="toolbar"><h2>设置</h2></div><div class="panel"><div class="row"><label>宝塔面板公开地址</label><input id="url" value="' +
            esc(d.panel_base_url || location.origin) +
            '"></div><div class="row"><label>新增客户端默认同步计划</label><input id="defaultSchedule" value="' +
            esc(d.default_sync_schedule || "0 * * * *") +
            '" placeholder="0 * * * *"><p class="muted">使用 crontab 五段格式，只作为新增客户端的默认值，不修改已有客户端。</p></div><div class="row"><label>日志保存时间（天）</label><input type="number" id="retention" min="1" max="3650" value="' +
            esc(d.pull_retention_days || 30) +
            '"><p class="muted">默认保存 30 天，客户端产生新日志时自动删除过期日志。</p></div><button class="btn" id="saveSettings">保存设置</button><span id="settingsSaved" class="good" style="display:none;margin-left:12px">设置已保存</span></div><div class="panel" style="margin-top:16px"><h3>数据维护</h3><p><button class="btn danger" id="clearEvents">清空日志</button></p><p class="muted">只删除日志，不影响客户端、证书、授权或设置。</p><hr><p><button class="btn danger" id="resetDatabase">完全重置数据库</button></p><p class="bad">永久删除全部客户端身份、纳管证书、授权、日志、审计记录和设置。</p></div><div class="panel" style="margin-top:16px"><h3 style="margin-top:0">关于</h3><div style="display:flex;align-items:center;gap:18px"><img src="/certhub-api?action=author_avatar" alt="白川枫" width="72" height="72" style="border-radius:50%;object-fit:cover;border:1px solid #e5e7eb"><div><b style="font-size:16px">白川枫</b><p class="muted" style="margin:5px 0 10px">@kot4ri · CertHub 作者</p><div style="display:flex;align-items:center;gap:12px"><a href="https://github.com/kot4ri" target="_blank" rel="noopener noreferrer" title="GitHub" aria-label="GitHub" style="display:inline-flex;color:#24292f"><svg width="25" height="25" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .7a11.5 11.5 0 0 0-3.64 22.41c.58.1.79-.25.79-.56v-2.23c-3.22.7-3.9-1.37-3.9-1.37-.52-1.34-1.29-1.7-1.29-1.7-1.05-.72.08-.71.08-.71 1.17.08 1.78 1.2 1.78 1.2 1.04 1.78 2.72 1.27 3.38.97.1-.75.4-1.27.74-1.56-2.57-.29-5.27-1.28-5.27-5.69 0-1.26.45-2.28 1.19-3.09-.12-.29-.52-1.47.11-3.05 0 0 .97-.31 3.16 1.18a10.97 10.97 0 0 1 5.75 0c2.19-1.49 3.16-1.18 3.16-1.18.63 1.58.23 2.76.11 3.05.74.81 1.19 1.83 1.19 3.09 0 4.42-2.71 5.39-5.29 5.68.42.36.79 1.06.79 2.14v3.17c0 .31.21.67.8.56A11.5 11.5 0 0 0 12 .7Z"/></svg></a><a href="https://zankyo.cc" target="_blank" rel="noopener noreferrer" title="zankyo.cc" aria-label="zankyo.cc" style="display:inline-flex;color:#20a53a"><svg width="25" height="25" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M2.8 12h18.4M12 2.5c2.5 2.7 3.8 5.9 3.8 9.5S14.5 18.8 12 21.5C9.5 18.8 8.2 15.6 8.2 12S9.5 5.2 12 2.5Z" fill="none" stroke="currentColor" stroke-width="1.8"/></svg></a></div></div></div></div>';
          const aboutDescription = main.lastElementChild.querySelector("p.muted");
          aboutDescription.innerHTML =
            '@kot4ri · <a href="https://github.com/kot4ri/certhub" target="_blank" rel="noopener noreferrer">查看本项目</a>';
          const updatePanel = document.createElement("div");
          updatePanel.className = "panel update-panel";
          updatePanel.innerHTML =
            '<div class="update-heading"><div><h3>插件更新</h3><p class="muted">自动检查 GitHub Release，并在安装前校验更新包。</p></div><span id="updateBadge" class="update-badge loading">检查中</span></div><div class="update-versions"><div class="version-card"><span>当前版本</span><strong id="currentVersion">—</strong></div><div class="version-arrow">→</div><div class="version-card"><span>最新版本</span><strong id="latestVersion">—</strong></div></div><div class="update-footer"><span id="updateMessage" class="muted">正在连接 GitHub…</span><div class="update-actions"><a id="releaseLink" class="btn btn-secondary" target="_blank" rel="noopener noreferrer" style="display:none">查看版本</a><button class="btn btn-secondary" id="checkUpdate">重新检查</button><button class="btn" id="installUpdate" style="display:none">立即更新</button></div></div>';
          main.insertBefore(updatePanel, main.lastElementChild);
          const loadUpdate = () => {
            const checkButton = document.getElementById("checkUpdate"),
              installButton = document.getElementById("installUpdate"),
              badge = document.getElementById("updateBadge"),
              message = document.getElementById("updateMessage"),
              releaseLink = document.getElementById("releaseLink");
            checkButton.disabled = true;
            badge.className = "update-badge loading";
            badge.textContent = "检查中";
            message.textContent = "正在连接 GitHub…";
            api("check_update")
              .then((update) => {
                document.getElementById("currentVersion").textContent = update.current_version;
                document.getElementById("latestVersion").textContent = update.latest_version;
                releaseLink.href = update.release_url;
                releaseLink.style.display = update.release_url ? "inline-flex" : "none";
                if (update.update_available) {
                  badge.className = "update-badge available";
                  badge.textContent = "发现新版本";
                  message.textContent = "新版本已发布，可以立即更新。";
                  installButton.style.display = "inline-flex";
                } else {
                  badge.className = "update-badge current";
                  badge.textContent = "已是最新";
                  message.textContent = "当前已是最新版本。";
                  installButton.style.display = "none";
                }
              })
              .catch((error) => {
                badge.className = "update-badge error";
                badge.textContent = "检查失败";
                message.textContent = error.message || String(error);
                installButton.style.display = "none";
              })
              .finally(() => (checkButton.disabled = false));
          };
          document.getElementById("checkUpdate").onclick = loadUpdate;
          document.getElementById("installUpdate").onclick = (event) => {
            if (!confirm("更新会覆盖当前插件文件并重启宝塔面板，确定继续？")) return;
            const button = event.currentTarget;
            button.disabled = true;
            button.textContent = "准备更新…";
            api("install_update")
              .then(() => {
                document.getElementById("updateMessage").textContent = "更新已启动，面板即将重启，请稍候…";
                button.textContent = "正在更新";
                setTimeout(() => location.reload(), 15000);
              })
              .catch((error) => {
                button.disabled = false;
                button.textContent = "立即更新";
                alert(error.message || error);
              });
          };
          loadUpdate();
          document.getElementById("saveSettings").onclick = (e) => {
            const button = e.currentTarget,
              hint = document.getElementById("settingsSaved");
            button.disabled = true;
            button.textContent = "保存中…";
            hint.style.display = "none";
            api("save_settings", {
              panel_base_url: document.getElementById("url").value,
              default_sync_schedule:
                document.getElementById("defaultSchedule").value,
              pull_retention_days: document.getElementById("retention").value,
            })
              .then(() => {
                button.textContent = "已保存";
                hint.style.display = "inline";
                setTimeout(() => {
                  button.disabled = false;
                  button.textContent = "保存设置";
                }, 1800);
              })
              .catch((x) => {
                button.disabled = false;
                button.textContent = "保存设置";
                alert(x.message || x);
              });
          };
          document.getElementById("clearEvents").onclick = () =>
            confirm("确定清空全部日志？此操作不可恢复。") &&
            api("clear_pull_events")
              .then(() => alert("日志已清空"))
              .catch(fail);
          document.getElementById("resetDatabase").onclick = () => {
            if (!confirm("这将完全重置 CertHub 数据库，是否继续？")) return;
            if (
              !confirm(
                "所有客户端身份和授权将立即失效，证书纳管与全部记录都会删除。是否继续？",
              )
            )
              return;
            if (!confirm("此操作永久且不可恢复。确定立即重置？")) return;
            api("reset_database")
              .then(() => {
                alert("数据库已完全重置");
                location.reload();
              })
              .catch(fail);
          };
        } catch (e) {
          fail(e);
        }
      }
      function onboarding() {
        onboardingLocked = true;
        document
          .querySelectorAll(".nav button")
          .forEach((b) => (b.disabled = true));
        main.innerHTML =
          '<div style="min-height:calc(100vh - 48px);display:flex;align-items:center;justify-content:center;padding:20px"><div class="panel" style="width:min(720px,100%);padding:28px"><div style="display:flex;align-items:center;justify-content:space-between;gap:16px;margin-bottom:22px"><div><h2 style="margin:0 0 6px">欢迎使用 CertHub</h2><span id="guideProgress" class="muted">1. 纳管证书　→　2. 添加下发服务　→　3. 获取安装命令</span></div><button class="btn" id="skipOnboarding" style="background:#909399">跳过引导</button></div><div id="guideContent"></div></div></div>';
        const content = document.getElementById("guideContent"),
          progress = document.getElementById("guideProgress"),
          finish = () => {
            onboardingLocked = false;
            document
              .querySelectorAll(".nav button")
              .forEach((b) => (b.disabled = false));
            dashboard();
          },
          showCertificates = () => {
            progress.textContent =
              "1. 纳管证书　→　2. 添加下发服务　→　3. 获取安装命令";
            content.innerHTML = '<p class="muted">正在扫描宝塔证书目录…</p>';
            api("discover_local")
              .then((rows) => {
                const valid = rows.filter((r) => !r.error);
                if (!valid.length) {
                  content.innerHTML =
                    '<div style="text-align:center;padding:24px"><div style="font-size:30px;color:#d48806">!</div><h3>未检测到宝塔面板有已签发的证书</h3><p class="muted">请先在宝塔面板申请或导入证书，然后重新检测。</p><button class="btn" id="guideRecheck">重新检测</button></div>';
                  content.querySelector("#guideRecheck").onclick =
                    showCertificates;
                  return;
                }
                content.innerHTML =
                  '<h3>选择需要纳管的证书</h3><p class="muted">检测到 ' +
                  valid.length +
                  ' 张有效证书，可选择多张用于首次下发。</p><div class="checks" style="display:grid;gap:10px;margin-bottom:16px">' +
                  valid
                    .map(
                      (r, i) =>
                        '<label style="padding:10px;border:1px solid #e5e7eb;border-radius:4px"><input type="checkbox" class="guide-certificate" value="' +
                        i +
                        '" ' +
                        (r.managed ? "checked" : "") +
                        '> <b>' +
                        esc(r.name) +
                        "</b> <span class=\"muted\">" +
                        esc((r.sans || []).join(", ")) +
                        (r.managed ? " · 已纳管" : "") +
                        "</span></label>",
                    )
                    .join("") +
                  '</div><button class="btn" id="guideManage">纳管选中证书并继续</button>';
                content.querySelector("#guideManage").onclick = (e) => {
                  const selected = [
                    ...content.querySelectorAll(".guide-certificate:checked"),
                  ].map((box) => valid[Number(box.value)]);
                  if (!selected.length) {
                    alert("请至少选择一张证书");
                    return;
                  }
                  e.currentTarget.disabled = true;
                  e.currentTarget.textContent = "正在纳管…";
                  Promise.all(
                    selected
                      .filter((item) => !item.managed)
                      .map((item) =>
                        api("import_local", {
                          path: item.path,
                          name: item.name,
                        }),
                      ),
                  )
                    .then(showService)
                    .catch((x) => {
                      e.currentTarget.disabled = false;
                      e.currentTarget.textContent = "纳管选中证书并继续";
                      alert(x.message || x);
                    });
                };
              })
              .catch(
                (e) =>
                  (content.innerHTML =
                    '<p class="bad">' +
                    esc(e.message || e) +
                    '</p><button class="btn" id="guideRetry">重新检测</button>'),
              );
          },
          showService = () => {
            progress.textContent =
              "✓ 纳管证书　→　2. 添加下发服务　→　3. 获取安装命令";
            content.innerHTML = '<p class="muted">正在加载客户端配置…</p>';
            Promise.all([api("certificates"), api("dashboard")])
              .then(([certs, defaults]) => {
                const initial = {
                  certificate_ids: certs.map((c) => Number(c.id)),
                  sync_schedule: defaults.default_sync_schedule || "0 * * * *",
                };
                content.innerHTML =
                  '<h3>添加第一个下发服务</h3><p class="muted">配置接收证书的服务器或 Windows 客户端。</p>' +
                  clientForm(initial, certs, false);
                bindClient(content, initial, false, (d) =>
                  api("complete_onboarding")
                    .then(() => {
                      progress.textContent =
                        "✓ 纳管证书　→　✓ 添加下发服务　→　✓ 获取安装命令";
                      content.innerHTML =
                        '<h3>下发服务已创建</h3><div class="result"></div><div class="actions"><button class="btn" id="enterDashboard">进入控制台</button></div>';
                      command(content.querySelector(".result"), d);
                      content.querySelector("#enterDashboard").onclick = finish;
                    })
                    .catch((x) => alert(x.message || x)),
                );
              })
              .catch((e) => {
                content.innerHTML =
                  '<p class="bad">' + esc(e.message || e) + "</p>";
              });
          };
        document.getElementById("skipOnboarding").onclick = () =>
          confirm("跳过后仍可在本地证书和客户端管理页面完成配置。确定跳过？") &&
          api("skip_onboarding")
            .then(finish)
            .catch((x) => alert(x.message || x));
        showCertificates();
      }
      async function startup() {
        try {
          const d = await api("dashboard");
          if (d.onboarding_completed) {
            dashboard();
            return;
          }
          onboarding();
        } catch (e) {
          fail(e);
        }
      }
      const pages = {
        dashboard,
        local,
        certificates,
        clients,
        events,
        settings,
      };
      document.querySelectorAll(".nav button[data-page]").forEach(
        (b) =>
          (b.onclick = () => {
            if (onboardingLocked) return;
            document
              .querySelectorAll(".nav button")
              .forEach((x) => x.classList.remove("active"));
            b.classList.add("active");
            pages[b.dataset.page]();
          }),
      );
      startup();
