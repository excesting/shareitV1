/**
 * app.js (Complete, Optimized, API-Driven)
 * Features: Sleek Centered Modals, Waste Tracking, AI Safety Stock, Excel Export, Streamlined Reports
 */

class IMSApp {
  constructor() {
    this.cachedInventory = [];
    this.cachedDailyLogs = [];
    this.boot();
  }

  // ==========================================
  // 1. MASTER BOOT SEQUENCE
  // ==========================================
  async boot() {
    this.setupNavigation();
    this.setupAnimations();
    this.setupCenteredConfirmModal(); // Installs the sleek popup

    // Fetch master data from SQLite FIRST so all pages can use it instantly
    await this.fetchInventoryFromDB();
    await this.fetchDailyLogsFromDB();

    // Initialize Pages
    this.initHomePage(); 
    this.initInventoryPage();
    this.initDailyLogPage();
    this.initFoodPredictionPage();
    this.initFoodAnalyticsPage();
    this.initReportsPage(); 
  }

  // ==========================================
  // 1.5 SLEEK CENTERED CONFIRM MODAL (NEW)
  // ==========================================
  setupCenteredConfirmModal() {
    const modalHtml = `
    <div id="sleekConfirmOverlay" class="custom-confirm-overlay">
        <div class="custom-confirm-box">
            <div id="sleekConfirmIcon" class="custom-confirm-icon"></div>
            <div id="sleekConfirmTitle" class="custom-confirm-title">Confirm</div>
            <div id="sleekConfirmMessage" class="custom-confirm-message">Are you sure?</div>
            <div class="custom-confirm-actions">
                <button id="sleekCancelBtn" class="btn-cancel-custom">Cancel</button>
                <button id="sleekConfirmBtn" class="btn-primary-custom">Confirm</button>
            </div>
        </div>
    </div>
    `;
    document.body.insertAdjacentHTML('beforeend', modalHtml);

    this.confirmOverlay = document.getElementById("sleekConfirmOverlay");
    this.confirmIcon = document.getElementById("sleekConfirmIcon");
    this.confirmTitle = document.getElementById("sleekConfirmTitle");
    this.confirmMessage = document.getElementById("sleekConfirmMessage");
    this.confirmBtn = document.getElementById("sleekConfirmBtn");
    this.cancelBtn = document.getElementById("sleekCancelBtn");

    // Close on cancel or clicking outside the box
    this.cancelBtn.addEventListener("click", () => this.closeConfirmModal());
    this.confirmOverlay.addEventListener("click", (e) => {
        if (e.target === this.confirmOverlay) this.closeConfirmModal();
    });
  }

  confirmAction(iconHtml, title, message, btnText, btnClass, callback) {
    this.confirmIcon.innerHTML = iconHtml;
    this.confirmTitle.innerHTML = title;
    this.confirmMessage.innerHTML = message;
    this.confirmBtn.className = btnClass;
    this.confirmBtn.innerHTML = btnText;

    // Clone and replace to reset event listeners safely
    const newBtn = this.confirmBtn.cloneNode(true);
    this.confirmBtn.parentNode.replaceChild(newBtn, this.confirmBtn);
    this.confirmBtn = newBtn;

    this.confirmBtn.addEventListener("click", async () => {
        this.closeConfirmModal();
        await callback();
    });

    this.confirmOverlay.classList.add("show");
  }

  closeConfirmModal() {
    this.confirmOverlay.classList.remove("show");
  }

  // ==========================================
  // 2. UI & NAVIGATION
  // ==========================================
  setupNavigation() {
    const currentPath = window.location.pathname;
    document.querySelectorAll(".sidebar-link").forEach((link) => {
      if (link.getAttribute("href") === currentPath) {
          link.classList.add("active");
      } else {
          link.classList.remove("active");
      }
    });
  }

  setupAnimations() {
    document.querySelectorAll(".card").forEach((card, i) => {
      card.style.animationDelay = `${i * 0.08}s`;
      card.classList.add("fade-in");
    });
  }

  // ==========================================
  // 3. DATABASE FETCHERS (Global Cache)
  // ==========================================
  async fetchInventoryFromDB(branchId = "all") {
    try {
      let url = "/api/inventory";
      if (branchId !== "all") {
        url += `?branch_id=${branchId}`;
      }
      
      const res = await fetch(url);
      const data = await res.json();
      if (data.success) {
        this.cachedInventory = data.items.map(item => ({
          id: item.id, 
          branch_id: item.branch_id,
          name: item.name, 
          unit: item.unit,
          stock: Number(item.stock), 
          min: Number(item.min_level), 
          max: Number(item.max_level),
          reorder_model: item.reorder_model || "rop",
          updatedAt: item.updated_at
        }));
      }
    } catch (e) {
      console.error("Failed to fetch inventory", e);
    }
  }

  async fetchDailyLogsFromDB() {
    try {
      const res = await fetch("/api/daily-logs");
      const data = await res.json();
      if (data.success) {
        this.cachedDailyLogs = data.logs.map(log => ({
          ...log, branchId: log.branch_id
        }));
      }
    } catch (e) {
      console.error("Failed to fetch daily logs", e);
    }
  }

  // ==========================================
  // 3.5 HOME PAGE DASHBOARD
  // ==========================================
  async initHomePage() {
    if (!document.getElementById("dashTotalProducts")) return;

    try {
      const res = await fetch("/api/dashboard-stats");
      const data = await res.json();
      if (data.success) {
        document.getElementById("dashTotalProducts").textContent = this.formatNumber(data.stats.totalProducts);
        document.getElementById("dashLowStock").textContent = this.formatNumber(data.stats.lowStockCount);
        document.getElementById("dashOutOfStock").textContent = this.formatNumber(data.stats.outOfStockCount);
        document.getElementById("dashTotalLogs").textContent = this.formatNumber(data.stats.totalLogs);
      }
    } catch (e) {
      console.error("Failed to load dashboard stats", e);
    }
  }

  // ==========================================
  // 4. INVENTORY SYSTEM
  // ==========================================
  initInventoryPage() {
    const tableBody = document.getElementById("inventoryTableBody");
    if (!tableBody) return; 

    this.inv = {
      tableBody,
      emptyState: document.getElementById("inventoryEmptyState"),
      branchFilter: document.getElementById("invBranchFilter"),
      search: document.getElementById("invSearch"),
      filter: document.getElementById("invFilter"),
      btnReset: document.getElementById("btnResetDataset"),
      modal: document.getElementById("inventoryModal"),
      form: document.getElementById("inventoryForm"),
      modalTitle: document.getElementById("modalTitle"),
      fieldId: document.getElementById("invId"),
      fieldBranch: document.getElementById("invBranch"),
      fieldName: document.getElementById("invName"),
      fieldUnit: document.getElementById("invUnit"),
      fieldReorderModel: document.getElementById("invReorderModel"),
      fieldStock: document.getElementById("invStock"),
      fieldMin: document.getElementById("invMin"),
      fieldMax: document.getElementById("invMax"),
      reorderBody: document.getElementById("reorderTableBody"),
      btnRefreshReorder: document.getElementById("btnRefreshReorder"),
      stats: {
        totalItems: document.getElementById("invTotalItems"),
        lowStock: document.getElementById("invLowStock"),
        outOfStock: document.getElementById("invOutOfStock"),
        actionRequired: document.getElementById("invActionRequired"),
      },
    };

    const btnAdd = document.getElementById("btnAddItem");
    if (btnAdd) {
      btnAdd.addEventListener("click", (e) => {
        e.preventDefault(); 
        this.openInventoryModal(null); 
      });
    }

    if (this.inv.modal) {
      this.inv.modal.addEventListener("click", (e) => {
        if (e.target?.dataset?.close === "true" || e.target?.closest?.('[data-close="true"]')) {
           this.closeInventoryModal();
        }
      });
    }

    this.inv.branchFilter?.addEventListener("change", () => this.renderInventory());
    
    if(this.inv.btnReset) {
        this.inv.btnReset.addEventListener("click", (e) => {
            this.confirmAction(
                '<i class="fas fa-exclamation-triangle text-danger"></i>',
                'Factory Reset Inventory',
                "Are you sure you want to reset the inventory to the default dataset? All current stock levels will be wiped to 0.", 
                "Yes, Reset", 
                "btn-danger-custom", 
                () => this.resetInventoryToDatasetViaApi()
            );
        });
    }

    this.inv.search?.addEventListener("input", () => this.renderInventory());
    this.inv.filter?.addEventListener("change", () => this.renderInventory());
    this.inv.btnRefreshReorder?.addEventListener("click", () => this.generateAIReorderRecommendations());
    
    // --- AUTOMATIC RECALCULATION TRIGGERS ---
    document.getElementById("rrServiceLevel")?.addEventListener("change", () => this.generateAIReorderRecommendations());
    document.getElementById("rrHorizon")?.addEventListener("change", () => this.generateAIReorderRecommendations());
    document.getElementById("rrLeadTime")?.addEventListener("change", () => this.generateAIReorderRecommendations());
    document.getElementById("rrBranch")?.addEventListener("change", () => this.generateAIReorderRecommendations());
    document.getElementById("rrItemFilter")?.addEventListener("change", () => this.generateAIReorderRecommendations());
    // ----------------------------------------
    
    this.inv.form?.addEventListener("submit", async (e) => {
      e.preventDefault();
      this.confirmAction(
        '<i class="fas fa-save text-primary"></i>',
        'Save Inventory Item',
        "Are you sure you want to update this item's details and stock levels?",
        "Save Item",
        "btn-primary-custom",
        async () => {
          await this.upsertInventoryItemViaApi();
        }
      );
    });

    this.renderInventory();
  }

  getDatasetDefaultIngredients() {
    return [
      { name: "Pork", unit: "kg" }, { name: "Chicken", unit: "kg" }, { name: "Beef", unit: "kg" },
      { name: "Lettuce", unit: "kg" }, { name: "Cucumber", unit: "kg" }, { name: "Kimchi", unit: "kg" },
      { name: "Mushroom", unit: "kg" }, { name: "Radish (pickled)", unit: "kg" },
      { name: "Cheese (melted cheese dip)", unit: "kg" },
      { name: "Fish Cake (Eomuk)", unit: "kg" },
      { name: "Tteok-bokki (Rice cake)", unit: "kg" }, { name: "Sweet Potato", unit: "kg" },
      { name: "Potato", unit: "kg" }, { name: "Rice (uncooked)", unit: "kg" },
      { name: "Juice", unit: "L" }, { name: "Shrimp", unit: "kg" },
      { name: "Scallop", unit: "kg" }, { name: "Mussel", unit: "kg" },
      { name: "Onion Leaks", unit: "kg" }, { name: "Corn", unit: "kg" }
    ];
  }

  async resetInventoryToDatasetViaApi() {
    const defaults = this.getDatasetDefaultIngredients().map((d) => ({
      id: this.makeId(), name: d.name, unit: d.unit, stock: 0, min: 0, max: 0, reorder_model: "rop"
    }));

    try {
      const res = await fetch("/api/inventory/reset", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items: defaults })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      this.showNotification("Inventory reset to dataset ingredients.", "success");
      await this.fetchInventoryFromDB(this.inv.branchFilter?.value || "all");
      this.renderInventory();
    } catch (e) {
      this.showNotification("Failed to reset inventory.", "error");
    }
  }

  openInventoryModal(item = null) {
    if (!this.inv || !this.inv.modal) return;
    
    const isEdit = item && typeof item === 'object' && item.id;

    this.inv.modalTitle.innerHTML = isEdit ? `<i class="fas fa-pen-to-square text-primary"></i> Edit Item` : `<i class="fas fa-plus text-primary"></i> Add Item`;
    this.inv.fieldId.value = isEdit ? item.id : "";
    this.inv.fieldBranch.value = isEdit ? item.branch_id : (this.inv.branchFilter?.value === "1" ? "1" : "0");
    this.inv.fieldName.value = isEdit ? item.name : "";
    this.inv.fieldUnit.value = isEdit ? (item.unit || "kg") : "kg";
    this.inv.fieldReorderModel.value = isEdit ? (item.reorder_model || "rop") : "rop";
    this.inv.fieldStock.value = isEdit ? (item.stock || 0) : 0;
    this.inv.fieldMin.value = isEdit ? (item.min || 0) : 0;
    this.inv.fieldMax.value = isEdit ? (item.max || 0) : 0;
    
    this.inv.modal.classList.remove("d-none");
    this.inv.modal.setAttribute("aria-hidden", "false");
  }

  closeInventoryModal() {
    if (!this.inv?.modal) return;
    this.inv.modal.classList.add("d-none");
    this.inv.modal.setAttribute("aria-hidden", "true");
  }

  async upsertInventoryItemViaApi() {
    const id = (this.inv.fieldId.value || "").trim() || this.makeId();
    const branch_id = parseInt(this.inv.fieldBranch.value);
    const name = (this.inv.fieldName.value || "").trim();
    const unit = this.inv.fieldUnit.value;
    const reorder_model = this.inv.fieldReorderModel.value; 
    const stock = parseFloat(this.inv.fieldStock.value);
    const min = parseFloat(this.inv.fieldMin.value);
    const max = parseFloat(this.inv.fieldMax.value);

    if (!name) return this.showNotification("Item name is required.", "error");

    try {
      this.showLoading(this.inv.form);
      const res = await fetch("/api/inventory", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id, branch_id, name, unit, stock, min, max, reorder_model })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);

      this.showNotification("Item saved successfully.", "success");
      this.closeInventoryModal();
      await this.fetchInventoryFromDB(this.inv.branchFilter?.value || "all");
      this.renderInventory();
    } catch (e) {
      this.showNotification("Failed to save item.", "error");
    } finally {
      this.hideLoading(this.inv.form);
    }
  }

  deleteInventoryItemViaApi(id) {
    this.confirmAction(
        '<i class="fas fa-trash-alt text-danger"></i>',
        'Delete Item',
        "Are you sure you want to permanently delete this inventory item?",
        "Delete",
        "btn-danger-custom",
        async () => {
            try {
              const res = await fetch(`/api/inventory/${id}`, { method: "DELETE" });
              const data = await res.json();
              if (!data.success) throw new Error(data.error);
              this.showNotification("Item removed.", "success");
              await this.fetchInventoryFromDB(this.inv.branchFilter?.value || "all");
              this.renderInventory();
            } catch (e) {
              this.showNotification("Failed to delete item.", "error");
            }
        }
    );
  }

  renderInventory() {
    if (!this.inv?.tableBody) return;
    let view = [...this.cachedInventory];
    const q = (this.inv.search?.value || "").trim().toLowerCase();
    const filter = this.inv.filter?.value || "all";
    const branchFilterValue = this.inv.branchFilter?.value || "all";

    if (branchFilterValue !== "all") {
      view = view.filter(x => Number(x.branch_id) === Number(branchFilterValue));
    }

    if (q) view = view.filter((x) => (x.name || "").toLowerCase().includes(q));
    if (filter === "low") view = view.filter((x) => (x.min ?? 0) > 0 && (x.stock ?? 0) <= (x.min ?? 0));
    
    view.sort((a, b) => (a.name || "").localeCompare(b.name || ""));

    if (this.inv.emptyState) this.inv.emptyState.classList.toggle("d-none", view.length !== 0);

    this.inv.tableBody.innerHTML = view.map((item) => {
      const isLow = item.stock <= item.min && item.stock > 0;
      const isOut = item.stock <= 0;
      let statusClass = "";
      if (isOut) statusClass = "text-danger font-bold";
      else if (isLow) statusClass = "text-warning font-bold";
      
      const bId = Number(item.branch_id);
      const branchBadge = bId === 1 
        ? '<span class="badge" style="background-color: #64748b; color: white;">Malvar</span>'
        : '<span class="badge" style="background-color: #3b82f6; color: white;">Lipa</span>';

      return `
      <tr>
        <td>${branchBadge}</td>
        <td><strong>${this.escapeHtml(item.name)}</strong></td>
        <td><span class="badge badge-neutral">${this.escapeHtml(item.unit)}</span></td>
        <td class="${statusClass}">${item.stock.toFixed(2)}</td>
        <td>${item.min.toFixed(2)}</td>
        <td>${item.max ?? 0}</td>
        <td>
          <div class="table-actions">
            <button class="btn btn-xs btn-secondary" onclick="window.app.openInventoryModal({id:'${item.id}', branch_id:${item.branch_id}, name:'${this.escapeHtml(item.name)}', unit:'${item.unit}', stock:${item.stock}, min:${item.min}, max:${item.max}, reorder_model:'${item.reorder_model || "rop"}'})"><i class="fas fa-pen"></i></button>
            <button class="btn btn-xs btn-danger" onclick="window.app.deleteInventoryItemViaApi('${item.id}')"><i class="fas fa-trash"></i></button>
          </div>
        </td>
      </tr>
    `}).join("");

    this.updateInventoryStats(view);

    const rrItemFilter = document.getElementById("rrItemFilter");
    if (rrItemFilter) {
      const currentSelection = rrItemFilter.value;
      const uniqueNames = [...new Set(view.map(i => i.name))].sort();
      rrItemFilter.innerHTML = `<option value="all">All Ingredients</option>` + 
        uniqueNames.map(name => `<option value="${this.escapeHtml(name)}">${this.escapeHtml(name)}</option>`).join("");
      if (uniqueNames.includes(currentSelection)) rrItemFilter.value = currentSelection;
    }
  }

  updateInventoryStats(items) {
    if (!this.inv?.stats) return;
    
    const lowStock = items.filter((x) => (x.min ?? 0) > 0 && (x.stock ?? 0) <= (x.min ?? 0) && (x.stock ?? 0) > 0).length;
    const outOfStock = items.filter((x) => (x.stock ?? 0) <= 0).length;
    const totalAction = lowStock + outOfStock;
    
    if (this.inv.stats.totalItems) this.inv.stats.totalItems.textContent = String(items.length);
    if (this.inv.stats.lowStock) this.inv.stats.lowStock.textContent = String(lowStock);
    if (this.inv.stats.outOfStock) this.inv.stats.outOfStock.textContent = String(outOfStock);
    if (this.inv.stats.actionRequired) this.inv.stats.actionRequired.textContent = String(totalAction);
  }

  // ==========================================
  // 5. AI SAFETY STOCK & REORDER MATH
  // ==========================================
  async generateAIReorderRecommendations() {
    if (!this.inv?.reorderBody) return;

    const horizon = Number(document.getElementById("rrHorizon")?.value) || 7;
    const leadTime = Number(document.getElementById("rrLeadTime")?.value) || 2;
    const branchId = Number(document.getElementById("rrBranch")?.value) || 0;
    const Z = Number(document.getElementById("rrServiceLevel")?.value) || 1.645;
    const selectedItem = document.getElementById("rrItemFilter")?.value || "all";

    const targetElement = this.inv.reorderBody.closest('.card');

    try {
      this.showLoading(targetElement, "Calculating AI Math Models...");

      let targetInventory = this.cachedInventory.filter(i => i.branch_id === branchId);
      
      if (selectedItem !== "all") {
        targetInventory = targetInventory.filter(i => i.name === selectedItem);
      }

      if (!targetInventory.length) {
        this.inv.reorderBody.innerHTML = `<tr><td colspan="9" class="text-center text-muted">No inventory items found for this selection.</td></tr>`;
        return;
      }

      let predictedData = null;
      try {
        const res = await fetch(`/api/latest-prediction?branch_id=${branchId}`);
        if (res.ok) {
           const data = await res.json();
           if (data.success && data.daily && data.daily.length > 0) predictedData = data;
        }
      } catch (e) {
        console.warn("No saved prediction found.", e);
      }

      const branchLogs = this.cachedDailyLogs.filter(l => l.branchId === branchId);

      const recs = targetInventory.map((item) => {
        const stock = Number(item.stock ?? 0);
        const targetName = item.name.toLowerCase();
        const modelType = item.reorder_model || "rop";

        const stdDev = this.computeStdDevFromLogs(branchLogs, item.name, 30);

        let avgDailyPred = 0;
        if (predictedData) {
          let totalPred = 0;
          for (const day of predictedData.daily) {
            const matchKey = Object.keys(day.ingredients).find((k) => {
              const cleanName = k.replace(/\s*\((kg|l|pcs)\)$/i, '').trim().toLowerCase();
              return cleanName === targetName;
            });
            
            if (matchKey) totalPred += Number(day.ingredients[matchKey]);
          }
          avgDailyPred = totalPred / predictedData.daily.length;
        } else {
          avgDailyPred = this.computeAvgDailyConsumptionFromLogs(branchLogs, item.name, 14) ?? 0;
        }

        let safetyStock = 0, dynamicROP = 0, dynamicMax = 0, suggestedOrder = 0;
        const horizonDemand = avgDailyPred * horizon;

        if (modelType === "newsvendor") {
          safetyStock = Z * stdDev; 
          
          dynamicMax = horizonDemand + safetyStock; 
          dynamicROP = (avgDailyPred * leadTime) + safetyStock;
          
          if (stock < dynamicMax) {
             suggestedOrder = Math.max(0, dynamicMax - stock);
          }
        } 
        else {
          let rawSafetyStock = Z * stdDev * Math.sqrt(leadTime);
          safetyStock = Math.min(rawSafetyStock, avgDailyPred * 3); 
          
          const expectedLeadTimeDemand = avgDailyPred * leadTime;
          dynamicROP = expectedLeadTimeDemand + safetyStock;
          dynamicMax = dynamicROP + horizonDemand;
          
          if (stock <= dynamicROP) {
            suggestedOrder = Math.max(0, dynamicMax - stock);
          }
        }

        let priorityScore = 50;
        let priorityLabel = "OK";
        
        if (suggestedOrder > 0) {
          if (stock <= (avgDailyPred * leadTime)) {
            priorityLabel = "Critical"; 
            priorityScore = 1;
          } else {
            priorityLabel = "High";
            priorityScore = 2;
          }
        }

        return {
          name: item.name, unit: item.unit || "", modelType: (modelType === 'rop' ? 'ROP' : 'NewsV'),
          stock, safetyStock, dynamicROP, dynamicMax, suggestedOrder, priorityLabel, priorityScore
        };
      }).sort((a, b) => a.priorityScore - b.priorityScore || b.suggestedOrder - a.suggestedOrder);

      this.inv.reorderBody.innerHTML = recs.map((r) => `
        <tr>
          <td><strong>${this.escapeHtml(r.name)}</strong></td>
          <td><span class="badge badge-info">${this.escapeHtml(r.unit)}</span></td>
          <td><span class="badge badge-neutral">${this.escapeHtml(r.modelType)}</span></td>
          <td>${this.formatNumber(r.stock.toFixed(2))}</td>
          <td><span class="text-warning font-weight-bold">${this.formatNumber(r.safetyStock.toFixed(2))}</span></td>
          <td><strong>${this.formatNumber(r.dynamicROP.toFixed(2))}</strong></td>
          <td>${this.formatNumber(r.dynamicMax.toFixed(2))}</td>
          <td><strong class="${r.suggestedOrder > 0 ? 'text-success' : ''}">${this.formatNumber(r.suggestedOrder.toFixed(2))}</strong></td>
          <td>${r.priorityLabel === 'OK' ? '<span class="badge badge-success">OK</span>' : (r.priorityLabel === 'Critical' ? '<span class="badge badge-danger">Critical</span>' : '<span class="badge badge-warning">High</span>')}</td>
        </tr>
      `).join("");

      if (predictedData) this.showNotification(`Loaded saved forecast from ${predictedData.start_date}.`, "success");

    } finally {
      this.hideLoading(targetElement);
    }
  }

  computeStdDevFromLogs(logs, productName, lookbackDays = 30) {
    if (!productName || !logs.length) return 0;
    const target = productName.trim().toLowerCase();
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - lookbackDays);

    const consumption = [];
    for (const entry of logs) {
      const d = new Date(entry.date);
      if (Number.isNaN(d.getTime()) || d < cutoff) continue;
      const matchKey = Object.keys(entry.items || {}).find((k) => k.trim().toLowerCase() === target);
      if (matchKey) {
        const v = Number(entry.items[matchKey]);
        if (Number.isFinite(v)) consumption.push(v);
      } else {
        consumption.push(0);
      }
    }

    if (consumption.length < 2) return 0; 
    const mean = consumption.reduce((a, b) => a + b, 0) / consumption.length;
    const variance = consumption.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / (consumption.length - 1);
    return Math.sqrt(variance);
  }

  computeAvgDailyConsumptionFromLogs(logs, productName, lookbackDays = 14) {
    if (!productName || !logs.length) return 0;
    const target = productName.trim().toLowerCase();
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - lookbackDays);

    let total = 0; let daysCount = 0;
    for (const entry of logs) {
      const d = new Date(entry.date);
      if (Number.isNaN(d.getTime()) || d < cutoff) continue;
      daysCount++;
      const matchKey = Object.keys(entry.items || {}).find((k) => k.trim().toLowerCase() === target);
      if (matchKey) total += (Number(entry.items[matchKey]) || 0);
    }
    return daysCount > 0 ? total / daysCount : 0;
  }

  // ==========================================
  // 6. DAILY LOGS SYSTEM
  // ==========================================
  initDailyLogPage() {
    const form = document.getElementById("dailyLogForm");
    if (!form) return;
    
    this.dl = { 
      form, 
      date: document.getElementById("dlDate"), 
      branch: document.getElementById("dlBranch"), 
      customers: document.getElementById("dlCustomers"), 
      remarks: document.getElementById("dlRemarks"),
      itemsBody: document.getElementById("dlItemsBody"), 
      historyBody: document.getElementById("dlHistoryBody"),
      resetBtn: document.getElementById("dlResetBtn"),
      clearAllBtn: document.getElementById("dlClearAllBtn"),
      kpiTotal: document.getElementById("dlTotalLogs"),
      kpiLastDate: document.getElementById("dlLastDate"),
      kpiLastBranch: document.getElementById("dlLastBranch"),
      kpiLastCustomers: document.getElementById("dlLastCustomers"),
    };

    const uniqueNames = new Set();
    this.dlIngredients = [];
    
    if (this.cachedInventory.length > 0) {
      this.cachedInventory.forEach(i => {
        if (!uniqueNames.has(i.name)) {
          uniqueNames.add(i.name);
          this.dlIngredients.push({ key: i.name, unit: i.unit });
        }
      });
      this.dlIngredients.sort((a,b) => a.key.localeCompare(b.key));
    } else {
      this.dlIngredients = [{ key: "Pork", unit: "kg" }, { key: "Chicken", unit: "kg" }];
    }

    if (this.dl.date && !this.dl.date.value) this.dl.date.value = new Date().toISOString().slice(0, 10);
    
    this.dl.date?.addEventListener("change", () => this.tryLoadDailyLog());
    this.dl.branch?.addEventListener("change", () => this.tryLoadDailyLog());
    this.dl.resetBtn?.addEventListener("click", () => this.resetDailyLogForm());
    
    if (this.dl.clearAllBtn) {
        this.dl.clearAllBtn.addEventListener("click", () => {
            this.confirmAction(
                '<i class="fas fa-exclamation-circle text-danger"></i>',
                'Clear Database',
                "Are you sure you want to delete ALL daily logs? This action cannot be undone.",
                "Delete All",
                "btn-danger-custom",
                () => this.clearAllDailyLogsViaApi()
            );
        });
    }

    this.dl.form.addEventListener("submit", async (e) => {
      e.preventDefault();
      this.confirmAction(
        '<i class="fas fa-save text-primary"></i>',
        'Save Daily Log',
        "Are you sure you want to save this log?",
        "Save Log",
        "btn-primary-custom",
        async () => {
          await this.saveDailyLogViaApi();
        }
      );
    });

    this.renderDailyLogItemRows();
    this.refreshDailyLogUI();
  }

  refreshDailyLogUI() {
    this.renderDailyLogHistory();
    this.updateDailyLogKpis();
    this.tryLoadDailyLog();
  }

  renderDailyLogItemRows() {
    if (!this.dl?.itemsBody) return;
    this.dl.itemsBody.innerHTML = this.dlIngredients.map(x => `
      <tr>
        <td><strong>${this.escapeHtml(x.key)}</strong></td>
        <td><span class="badge badge-success">${this.escapeHtml(x.unit)}</span></td>
        <td><input type="number" class="form-control form-control-sm" data-dl-item="${this.escapeHtml(x.key)}" min="0" step="0.01" value="0" /></td>
        <td><input type="number" class="form-control form-control-sm border-warning text-warning" data-dl-waste="${this.escapeHtml(x.key)}" min="0" step="0.01" value="0" /></td>
      </tr>
    `).join("");
  }

  tryLoadDailyLog() {
    const date = this.dl.date?.value;
    const branchId = Number(this.dl.branch?.value);
    if (!date || Number.isNaN(branchId)) return;

    const existing = this.cachedDailyLogs.find((x) => x.date === date && x.branchId === branchId);
    if (!existing) {
      this.dl.itemsBody?.querySelectorAll("input").forEach(inp => inp.value = 0);
      return;
    }

    this.dl.customers.value = existing.customers ?? 0;
    this.dl.remarks.value = existing.remarks ?? "Normal";
    this.dl.itemsBody?.querySelectorAll("tr").forEach(tr => {
      const qtyInp = tr.querySelector('input[data-dl-item]');
      const wasteInp = tr.querySelector('input[data-dl-waste]');
      if (!qtyInp) return;

      const key = qtyInp.getAttribute("data-dl-item");
      qtyInp.value = existing.items?.[key] ?? 0;
      if (wasteInp) wasteInp.value = existing.waste?.[key] ?? 0;
    });
  }

  async saveDailyLogViaApi() {
    const date = this.dl.date?.value;
    const branchId = Number(this.dl.branch?.value);
    const customers = Number(this.dl.customers?.value);
    const remarks = this.dl.remarks?.value || "Normal";

    const items = {};
    const waste = {};
    
    this.dl.itemsBody?.querySelectorAll("tr").forEach(tr => {
      const qtyInp = tr.querySelector('input[data-dl-item]');
      const wasteInp = tr.querySelector('input[data-dl-waste]');
      if (qtyInp && wasteInp) {
        const q = Number(qtyInp.value);
        const w = Number(wasteInp.value);
        const key = qtyInp.getAttribute("data-dl-item");
        
        if (q > 0) items[key] = q;
        if (w > 0) waste[key] = w;
      }
    });

    try {
      this.showLoading(this.dl.form);
      const res = await fetch("/api/daily-logs", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ date, branch_id: branchId, customers, remarks, items, waste })
      });
      const data = await res.json();
      if (!data.success) throw new Error(data.error);
      
      this.showNotification("Daily log saved to database!", "success");
      await this.fetchDailyLogsFromDB();
      this.refreshDailyLogUI();
    } catch (e) {
      this.showNotification("Failed to save log.", "error");
    } finally {
      this.hideLoading(this.dl.form);
    }
  }

  deleteDailyLogViaApi(id) {
    this.confirmAction(
        '<i class="fas fa-trash-alt text-danger"></i>',
        'Delete Log',
        "Are you sure you want to delete this log? The consumed quantities will be refunded back to your inventory stock.",
        "Delete",
        "btn-danger-custom",
        async () => {
            try {
              const res = await fetch(`/api/daily-logs/${id}`, { method: "DELETE" });
              const data = await res.json();
              if(!data.success) throw new Error(data.error);
              
              this.showNotification("Log deleted.", "success");
              await this.fetchDailyLogsFromDB();
              this.refreshDailyLogUI();
            } catch (e) {
              this.showNotification("Failed to delete log.", "error");
            }
        }
    );
  }

  async clearAllDailyLogsViaApi() {
    try {
      const res = await fetch(`/api/daily-logs/clear`, { method: "DELETE" });
      const data = await res.json();
      if(!data.success) throw new Error(data.error);
      
      this.showNotification("Database logs cleared.", "success");
      await this.fetchDailyLogsFromDB();
      this.refreshDailyLogUI();
    } catch (e) {
      this.showNotification("Failed to clear logs.", "error");
    }
  }

  resetDailyLogForm() {
    if (!this.dl) return;
    this.dl.customers.value = 0;
    this.dl.remarks.value = "Normal";
    this.dl.itemsBody?.querySelectorAll("input").forEach(inp => inp.value = 0);
  }

  renderDailyLogHistory() {
    if (!this.dl?.historyBody) return;
    if (!this.cachedDailyLogs.length) {
      this.dl.historyBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No logs in database.</td></tr>`;
      return;
    }

    const unitOf = Object.fromEntries(this.dlIngredients.map(x => [x.key, x.unit]));

    this.dl.historyBody.innerHTML = this.cachedDailyLogs.map(l => {
      const ranked = Object.entries(l.items || {})
        .map(([name, qty]) => ({ name, qty: Number(qty) || 0, unit: unitOf[name] || "" }))
        .filter(x => x.qty > 0).sort((a, b) => b.qty - a.qty).slice(0, 3);
      const topText = ranked.length ? ranked.map(x => `${x.name}: ${x.qty.toFixed(2)} ${x.unit}`).join(", ") : "-";

      return `
        <tr>
          <td>${this.escapeHtml(l.date)}</td>
          <td><span class="badge badge-info">${l.branchId === 0 ? "Lipa" : "Malvar"}</span></td>
          <td><strong>${this.formatNumber(l.customers)}</strong></td>
          <td>${this.escapeHtml(l.remarks)}</td>
          <td>${this.escapeHtml(topText)}</td>
          <td>
            <button class="btn btn-xs btn-danger" onclick="window.app.deleteDailyLogViaApi(${l.id})"><i class="fas fa-trash"></i></button>
          </td>
        </tr>`;
    }).join("");
  }

  updateDailyLogKpis() {
    if (!this.dl) return;
    const logs = this.cachedDailyLogs;
    if (this.dl.kpiTotal) this.dl.kpiTotal.textContent = this.formatNumber(logs.length);

    const latest = logs[0]; 
    if (!latest) {
      if (this.dl.kpiLastDate) this.dl.kpiLastDate.textContent = "-";
      if (this.dl.kpiLastBranch) this.dl.kpiLastBranch.textContent = "-";
      if (this.dl.kpiLastCustomers) this.dl.kpiLastCustomers.textContent = "-";
      return;
    }

    if (this.dl.kpiLastDate) this.dl.kpiLastDate.textContent = latest.date;
    if (this.dl.kpiLastBranch) this.dl.kpiLastBranch.textContent = latest.branchId === 0 ? "Lipa" : "Malvar";
    if (this.dl.kpiLastCustomers) this.dl.kpiLastCustomers.textContent = this.formatNumber(latest.customers);
  }

  // ==========================================
  // 7. FOOD PREDICTION SYSTEM
  // ==========================================
  initFoodPredictionPage() {
    const form = document.getElementById("predictionForm");
    if (!form) return;

    this.fp = {
      form,
      startDate: document.getElementById("pfStartDate"),
      horizon: document.getElementById("pfHorizon"),
      branch: document.getElementById("pfBranch"),
      remarks: document.getElementById("pfRemarks"),
      derived: document.getElementById("pfDerived"),
      mode: document.getElementById("pfMode"),
      item: document.getElementById("pfItem"),
      itemWrap: document.getElementById("pfItemWrap"),
      outCustomers: document.getElementById("predCustomers"),
      outSummary: document.getElementById("predSummary"),
      dailyCards: document.getElementById("predDailyCards"),
      btnClearHistory: document.getElementById("btnClearPredHistory"),
      historyBody: document.getElementById("predHistoryBody"),
    };

    const uniqueNames = new Set();
    this.fpIngredients = [];
    
    if (this.cachedInventory.length > 0) {
      this.cachedInventory.forEach(i => {
        if (!uniqueNames.has(i.name)) {
          uniqueNames.add(i.name);
          this.fpIngredients.push({ key: i.name, unit: i.unit });
        }
      });
      this.fpIngredients.sort((a,b) => a.key.localeCompare(b.key));
    } else {
      this.fpIngredients = [{ key: "Pork", unit: "kg" }, { key: "Chicken", unit: "kg" }];
    }

    if (this.fp.item) {
      this.fp.item.innerHTML = this.fpIngredients
        .map((x, i) => `<option value="${this.escapeHtml(x.key)}"${i === 0 ? " selected" : ""}>${this.escapeHtml(x.key)} (${this.escapeHtml(x.unit)})</option>`)
        .join("");
    }

    if (this.fp.startDate && !this.fp.startDate.value) this.fp.startDate.value = new Date().toISOString().slice(0, 10);

    this.updateDerivedPredictionFields();
    this.updatePredictionModeUI();
    this.fetchPredictionHistory();

    // Event Listeners
    this.fp.branch?.addEventListener("change", () => this.fetchPredictionHistory());
    this.fp.startDate?.addEventListener("change", () => this.updateDerivedPredictionFields());
    this.fp.horizon?.addEventListener("change", () => this.updateDerivedPredictionFields());
    this.fp.mode?.addEventListener("change", () => this.updatePredictionModeUI());
    
    if(this.fp.btnClearHistory) {
        this.fp.btnClearHistory.addEventListener("click", () => {
             this.confirmAction(
                '<i class="fas fa-exclamation-circle text-danger"></i>',
                'Clear All Forecasts',
                "Are you sure you want to clear ALL prediction history? This cannot be undone.",
                "Clear History",
                "btn-danger-custom",
                () => this.clearPredictionHistory()
             );
        });
    }
    
    this.fp.form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await this.runFoodForecastViaApi();
    });
  }

  computeEndDateFromHorizon(startDateStr, horizonDays) {
    const sd = new Date(startDateStr);
    if (Number.isNaN(sd.getTime())) return null;
    const hd = Number(horizonDays);
    if (!Number.isFinite(hd) || hd <= 0) return null;
    const ed = new Date(sd);
    ed.setDate(ed.getDate() + (hd - 1));
    return ed.toISOString().slice(0, 10);
  }

  updateDerivedPredictionFields() {
    if (!this.fp?.startDate || !this.fp?.horizon || !this.fp?.derived) return;
    const s = this.fp.startDate.value;
    const h = Number(this.fp.horizon.value);
    const endStr = this.computeEndDateFromHorizon(s, h);
    if (!endStr) {
      this.fp.derived.innerHTML = `<small class="text-muted">Range details will show here.</small>`;
      return;
    }
    const sWeekday = new Date(s).toLocaleDateString("en-US", { weekday: "short" });
    const eWeekday = new Date(endStr).toLocaleDateString("en-US", { weekday: "short" });
    this.fp.derived.innerHTML = `<small class="text-muted">Range: <b>${this.escapeHtml(s)}</b> (${this.escapeHtml(sWeekday)}) → <b>${this.escapeHtml(endStr)}</b> (${this.escapeHtml(eWeekday)}) • Days: <b>${this.escapeHtml(String(h))}</b></small>`;
  }

  updatePredictionModeUI() {
    if (!this.fp?.mode || !this.fp?.itemWrap) return;
    this.fp.itemWrap.style.display = this.fp.mode.value === "one" ? "block" : "none";
  }

  async runFoodForecastViaApi() {
    const startDate = this.fp.startDate?.value;
    const horizonDays = Number(this.fp.horizon?.value);
    const branchId = Number(this.fp.branch?.value);
    const remarks = this.fp.remarks?.value || "Normal";
    const mode = this.fp.mode?.value || "all";
    const selectedItem = this.fp.item?.value || "";
    const endDate = this.computeEndDateFromHorizon(startDate, horizonDays);

    const targetElement = this.fp.form.closest('.card') || this.fp.form;

    try {
      this.showLoading(targetElement, "AI is analyzing historical data...");
      
      const res = await fetch("/api/predict-range", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ start_date: startDate, end_date: endDate, branch_id: branchId, remarks }),
      });
      const result = await res.json();
      if (!res.ok || !result.success) throw new Error(result.error || `Forecast failed.`);

      const totalCustomers = Number(result?.totals?.customers ?? 0);
      if (this.fp.outCustomers) this.fp.outCustomers.textContent = this.formatNumber(Math.round(totalCustomers));

      const branchName = branchId === 0 ? "Lipa" : "Malvar";
      if (this.fp.outSummary) {
        this.fp.outSummary.innerHTML = `
          <p><strong>Branch:</strong> ${this.escapeHtml(branchName)}</p>
          <p><strong>Range:</strong> ${this.escapeHtml(startDate)} → ${this.escapeHtml(endDate)}</p>
          <p><strong>Total Predicted Customers:</strong> ${this.formatNumber(Math.round(totalCustomers))}</p>
        `;
      }

      this.renderDailyPredictionCards(result.daily || [], mode, selectedItem);
      await this.fetchPredictionHistory();
      this.showNotification("Forecast saved to database successfully.", "success");
      
    } catch (err) {
      this.showNotification(err.message, "error");
    } finally {
      this.hideLoading(targetElement);
    }
  }

  renderDailyPredictionCards(dailyRows, mode, selectedItem) {
    if (!this.fp?.dailyCards) return;
    this.fp.dailyCards.innerHTML = dailyRows.map((day) => {
      
      let ingredientsList = Object.entries(day.ingredients || {}).map(([rawName, qty]) => {
        const cleanName = rawName.replace(/\s*\((kg|l|pcs)\)$/i, '').trim();
        return { name: cleanName, qty: Number(qty) || 0 };
      });

      let displayIngredients = [];

      if (mode === "one" && selectedItem) {
        const found = ingredientsList.find(x => x.name.toLowerCase() === selectedItem.toLowerCase());
        if (found) {
          displayIngredients.push(found);
        } else {
          displayIngredients.push({ name: selectedItem, qty: 0 }); 
        }
      } else {
        displayIngredients = ingredientsList.sort((a, b) => b.qty - a.qty).slice(0, 5);
      }

      let tableHtml = displayIngredients.map(x => `
        <tr>
          <td><strong>${this.escapeHtml(x.name)}</strong></td>
          <td>${this.formatNumber(x.qty.toFixed(2))}</td>
        </tr>
      `).join("");
      
      return `
        <div class="card mb-4">
          <div class="card-header">
            <h3 class="card-title"><i class="fas fa-calendar-day text-primary"></i> ${this.escapeHtml(day.date)}</h3>
            <p class="card-subtitle">Predicted customers: <strong>${this.formatNumber(Math.round(day.customers || 0))}</strong></p>
          </div>
          <div class="p-3">
            <table class="table">
              <thead><tr><th>Ingredient</th><th>Predicted Qty</th></tr></thead>
              <tbody>${tableHtml || `<tr><td colspan="2">No data</td></tr>`}</tbody>
            </table>
          </div>
        </div>
      `;
    }).join("");
  }

  async fetchPredictionHistory() {
    if (!this.fp?.historyBody) return;
    
    const branchId = this.fp.branch ? this.fp.branch.value : "0"; 
    
    try {
      const res = await fetch(`/api/prediction-history?branch_id=${branchId}`);
      const data = await res.json();
      if (!data.success || !data.history.length) {
        this.fp.historyBody.innerHTML = `<tr><td colspan="6" class="text-center text-muted">No database history yet.</td></tr>`;
        return;
      }
      this.fp.historyBody.innerHTML = data.history.map(e => `
        <tr>
          <td>${this.escapeHtml(e.start_date)} → ${this.escapeHtml(e.end_date)}</td>
          <td><span class="badge badge-info">${e.branch_id === 0 ? "Lipa" : "Malvar"}</span></td>
          <td>${this.escapeHtml(e.remarks || "Normal")}</td>
          <td><strong>${this.formatNumber(e.total_customers)}</strong></td>
          <td>${this.escapeHtml(e.top_items || "-")}</td>
          <td>
            <button class="btn btn-xs btn-danger" onclick="window.app.deletePredictionHistoryEntry(${e.id})"><i class="fas fa-trash"></i></button>
          </td>
        </tr>
      `).join("");
    } catch (e) {
      this.fp.historyBody.innerHTML = `<tr><td colspan="6" class="text-center text-danger">Failed to load history from database.</td></tr>`;
    }
  }

  deletePredictionHistoryEntry(id) {
    this.confirmAction(
        '<i class="fas fa-trash-alt text-danger"></i>',
        'Delete Forecast',
        "Are you sure you want to delete this forecast from the database?",
        "Delete",
        "btn-danger-custom",
        async () => {
            try {
              const res = await fetch(`/api/prediction-history/${id}`, { method: "DELETE" });
              const data = await res.json();
              if(!data.success) throw new Error(data.error);
              
              await this.fetchPredictionHistory();
              this.showNotification("Record deleted from database.", "success");
            } catch (e) {
              this.showNotification("Failed to delete record.", "error");
            }
        }
    );
  }

  async clearPredictionHistory() {
    try {
      const res = await fetch(`/api/prediction-history/clear`, { method: "DELETE" });
      const data = await res.json();
      if(!data.success) throw new Error(data.error);
      
      await this.fetchPredictionHistory();
      this.showNotification("Database history cleared.", "success");
    } catch (e) {
      this.showNotification("Failed to clear history.", "error");
    }
  }

  // ==========================================
  // 9. ANALYTICS DASHBOARD
  // ==========================================
  initFoodAnalyticsPage() {
    const container = document.getElementById("foodAnalyticsFilters");
    if (!container) return;

    this.fa = {
      branch: document.getElementById("faBranch"),
      startDate: document.getElementById("faStartDate"),
      endDate: document.getElementById("faEndDate"),
      item: document.getElementById("faItem"),
      btnApply: document.getElementById("faApply"),
      btnReset: document.getElementById("faReset"),
      stats: {
        totalCust: document.getElementById("faTotalCustomers"),
        avgCust: document.getElementById("faAvgCustomers"),
        selectedTotal: document.getElementById("faSelectedTotal"),
        daysCovered: document.getElementById("faDaysCovered")
      },
      tableBody: document.getElementById("faItemsTableBody")
    };

    this.charts = {};

    Chart.defaults.font.family = "'Inter', sans-serif";
    Chart.defaults.color = "#6b7280";
    Chart.defaults.scale.grid.color = "#f3f4f6";

    if (this.fa.item) {
      const uniqueNames = new Set();
      const sortedIngredients = [];
      this.cachedInventory.forEach(i => {
        if (!uniqueNames.has(i.name)) {
          uniqueNames.add(i.name);
          sortedIngredients.push(i);
        }
      });
      sortedIngredients.sort((a, b) => a.name.localeCompare(b.name));
      
      this.fa.item.innerHTML = sortedIngredients.length > 0 
        ? sortedIngredients.map(i => `<option value="${i.name}">${i.name}</option>`).join("")
        : `<option value="Pork">Pork</option>`;
    }

    this.resetAnalyticsFilters();

    this.fa.btnApply.addEventListener("click", () => this.renderAnalytics());
    this.fa.btnReset.addEventListener("click", () => {
      this.resetAnalyticsFilters();
      this.renderAnalytics();
    });

    this.renderAnalytics();
  }

  resetAnalyticsFilters() {
    const today = new Date();
    const thirtyDaysAgo = new Date();
    thirtyDaysAgo.setDate(today.getDate() - 30);
    
    this.fa.endDate.value = today.toISOString().slice(0, 10);
    this.fa.startDate.value = thirtyDaysAgo.toISOString().slice(0, 10);
    this.fa.branch.value = "all";
    if (this.fa.item.options.length > 0) this.fa.item.selectedIndex = 0;
  }

  renderAnalytics() {
    const logs = this.cachedDailyLogs;
    if (!logs || logs.length === 0) {
      console.warn("No daily logs available for analytics.");
      return;
    }

    const bVal = this.fa.branch.value;
    const sDate = this.fa.startDate.value;
    const eDate = this.fa.endDate.value;
    const selectedItem = this.fa.item.value;

    const filtered = logs.filter(log => {
      if (bVal !== "all" && String(log.branchId) !== bVal) return false;
      if (sDate && log.date < sDate) return false;
      if (eDate && log.date > eDate) return false;
      return true;
    }).sort((a, b) => new Date(a.date) - new Date(b.date)); 

    const totalDays = new Set(filtered.map(l => l.date)).size;
    const totalCustomers = filtered.reduce((sum, l) => sum + (l.customers || 0), 0);
    const avgCustomers = totalDays > 0 ? (totalCustomers / totalDays).toFixed(0) : 0;
    
    let selectedItemTotal = 0;
    const ingredientTotals = {};

    filtered.forEach(log => {
      if (log.items && log.items[selectedItem]) {
        selectedItemTotal += Number(log.items[selectedItem]);
      }
      
      for (const [key, qty] of Object.entries(log.items || {})) {
        ingredientTotals[key] = (ingredientTotals[key] || 0) + Number(qty);
      }
    });

    this.fa.stats.totalCust.textContent = this.formatNumber(totalCustomers);
    this.fa.stats.avgCust.textContent = this.formatNumber(avgCustomers);
    this.fa.stats.selectedTotal.textContent = this.formatNumber(selectedItemTotal.toFixed(2));
    this.fa.stats.daysCovered.textContent = String(totalDays);

    const dates = filtered.map(l => l.date);
    const customersData = filtered.map(l => l.customers || 0);
    const itemTrendData = filtered.map(l => l.items?.[selectedItem] || 0);

    const sortedIngredients = Object.entries(ingredientTotals)
      .sort((a, b) => b[1] - a[1]);
    const topIngredients = sortedIngredients.slice(0, 7); 

    this.drawChart("faCustomersChart", "customers", {
      type: "line",
      data: {
        labels: dates,
        datasets: [{
          label: "Customers",
          data: customersData,
          borderColor: "#2563eb",
          backgroundColor: "rgba(37, 99, 235, 0.1)",
          borderWidth: 2,
          pointBackgroundColor: "#ffffff",
          pointBorderColor: "#2563eb",
          pointBorderWidth: 2,
          pointRadius: 4,
          fill: true,
          tension: 0.4 
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } }, 
          y: { beginAtZero: true, grid: { borderDash: [4, 4] } }
        }
      }
    });

    this.drawChart("faTopItemsChart", "topItems", {
      type: "bar",
      data: {
        labels: topIngredients.map(i => i[0]),
        datasets: [{
          label: "Quantity Consumed",
          data: topIngredients.map(i => i[1]),
          backgroundColor: "#3b82f6",
          borderRadius: 6, 
          borderSkipped: false
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { borderDash: [4, 4] } }
        }
      }
    });

    this.drawChart("faItemTrendChart", "itemTrend", {
      type: "line",
      data: {
        labels: dates,
        datasets: [{
          label: selectedItem,
          data: itemTrendData,
          borderColor: "#10b981", 
          backgroundColor: "rgba(16, 185, 129, 0.1)",
          borderWidth: 2,
          pointBackgroundColor: "#ffffff",
          pointBorderColor: "#10b981",
          pointRadius: 4,
          fill: true,
          tension: 0.4
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { borderDash: [4, 4] } }
        }
      }
    });

    const scatterData = filtered.map(l => ({
      x: l.customers || 0,
      y: l.items?.[selectedItem] || 0
    }));

    this.drawChart("faScatterChart", "scatter", {
      type: "scatter",
      data: {
        datasets: [{
          label: `Customers vs ${selectedItem}`,
          data: scatterData,
          backgroundColor: "rgba(245, 158, 11, 0.7)", 
          borderColor: "#f59e0b",
          pointRadius: 6,
          pointHoverRadius: 8
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { title: { display: true, text: 'Customers' }, grid: { display: false } },
          y: { title: { display: true, text: 'Qty Consumed' }, beginAtZero: true, grid: { borderDash: [4, 4] } }
        }
      }
    });

    this.fa.tableBody.innerHTML = sortedIngredients.length === 0 
      ? `<tr><td colspan="3" class="text-center text-muted">No data found for this range.</td></tr>`
      : sortedIngredients.map((item, index) => {
          const invItem = this.cachedInventory.find(i => i.name === item[0]);
          const unit = invItem ? invItem.unit : "";
          return `
            <tr>
              <td><strong>#${index + 1}</strong></td>
              <td>${this.escapeHtml(item[0])}</td>
              <td><span class="badge badge-info">${this.formatNumber(item[1].toFixed(2))} ${unit}</span></td>
            </tr>`;
        }).join("");
  }

  drawChart(canvasId, chartKey, config) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    
    if (this.charts[chartKey]) {
      this.charts[chartKey].destroy();
    }
    
    this.charts[chartKey] = new Chart(ctx, config);
  }

  // ==========================================
  // 10. REPORTS ENGINE (Excel Export Built-in)
  // ==========================================
  initReportsPage() {
    const form = document.getElementById("reportForm");
    if (!form) return;

    this.rep = {
      form,
      type: document.getElementById("repType"),
      branch: document.getElementById("repBranch"),
      startDate: document.getElementById("repStartDate"),
      endDate: document.getElementById("repEndDate"),
      outputCard: document.getElementById("reportOutputCard"),
      outputTitle: document.getElementById("reportOutputTitle"),
      timestamp: document.getElementById("reportTimestamp"),
      head: document.getElementById("reportHead"),
      body: document.getElementById("reportBody"),
      btnPrint: document.getElementById("btnPrintReport"),
      btnExport: document.getElementById("btnExportReport") 
    };

    if (this.rep.btnPrint) {
        this.rep.btnPrint.addEventListener("click", () => window.print());
    }

    if (this.rep.btnExport) {
        this.rep.btnExport.addEventListener("click", () => this.exportReportToCSV());
    }

    this.rep.form.addEventListener("submit", async (e) => {
      e.preventDefault();
      await this.generateReportViaApi();
    });
  }

  async generateReportViaApi() {
    const payload = {
      type: this.rep.type.value,
      branch_id: this.rep.branch.value,
      start_date: this.rep.startDate.value,
      end_date: this.rep.endDate.value
    };

    try {
      this.showLoading(this.rep.form, "Crunching report data...");
      const res = await fetch("/api/reports/generate", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      
      if (!data.success) throw new Error(data.error);

      this.rep.outputTitle.innerHTML = `<i class="fas fa-file-alt text-primary"></i> ${data.title}`;
      this.rep.timestamp.textContent = new Date().toLocaleString();
      
      this.rep.head.innerHTML = `<tr>${data.columns.map(c => `<th>${this.escapeHtml(c)}</th>`).join('')}</tr>`;
      
      if (data.data.length === 0) {
          this.rep.body.innerHTML = `<tr><td colspan="${data.columns.length}" class="text-center text-muted">No data found for this report.</td></tr>`;
      } else {
          this.rep.body.innerHTML = data.data.map(row => `<tr>${row.map(cell => `<td>${this.escapeHtml(String(cell))}</td>`).join('')}</tr>`).join('');
      }

      this.rep.outputCard.classList.remove("d-none");
      
      if (this.rep.btnPrint) this.rep.btnPrint.classList.remove("d-none");
      if (this.rep.btnExport) this.rep.btnExport.classList.remove("d-none"); 
      
      this.showNotification("Report generated successfully.", "success");

    } catch (e) {
      this.showNotification(e.message, "error");
    } finally {
      this.hideLoading(this.rep.form);
    }
  }

  exportReportToCSV() {
    if (!this.rep || !this.rep.head || !this.rep.body) return;

    let csvContent = [];
    
    let headers = [];
    this.rep.head.querySelectorAll("th").forEach(th => {
        headers.push('"' + th.innerText.replace(/"/g, '""') + '"');
    });
    csvContent.push(headers.join(","));

    this.rep.body.querySelectorAll("tr").forEach(tr => {
        let rowData = [];
        tr.querySelectorAll("td").forEach(td => {
            rowData.push('"' + td.innerText.replace(/"/g, '""') + '"');
        });
        if (rowData.length > 0) csvContent.push(rowData.join(","));
    });

    const csvString = csvContent.join("\r\n");
    const blob = new Blob([csvString], { type: "text/csv;charset=utf-8;" });
    
    const reportTypeSelect = this.rep.type;
    const reportTypeName = reportTypeSelect.options[reportTypeSelect.selectedIndex].text.replace(/[^a-zA-Z0-9]/g, "_").toLowerCase();
    const timestamp = new Date().toISOString().slice(0, 10);
    const filename = `IMS_Report_${reportTypeName}_${timestamp}.csv`;

    const link = document.createElement("a");
    const url = URL.createObjectURL(blob);
    link.setAttribute("href", url);
    link.setAttribute("download", filename);
    link.style.visibility = "hidden";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    this.showNotification("Excel CSV Downloaded Successfully!", "success");
  }

  // ==========================================
  // HELPERS & UTILITIES
  // ==========================================
  makeId() { return Math.random().toString(16).slice(2) + Date.now().toString(16); }

  showNotification(message, type = "success") {
      let container = document.getElementById('toast-container');
      if (!container) {
          container = document.createElement('div');
          container.id = 'toast-container';
          document.body.appendChild(container);
      }

      const toast = document.createElement('div');
      toast.className = `toast-card toast-${type}`;

      const iconClass = type === 'success' ? 'fas fa-check-circle' : 'fas fa-exclamation-circle';
      const titleText = type === 'success' ? 'Success' : 'Error';

      toast.innerHTML = `
          <div class="toast-icon">
              <i class="${iconClass}"></i>
          </div>
          <div class="toast-content">
              <div class="toast-title">${titleText}</div>
              <div class="toast-message">${message}</div>
          </div>
          <button class="toast-close">&times;</button>
      `;

      toast.querySelector('.toast-close').addEventListener('click', () => {
          toast.classList.add('hide');
          setTimeout(() => toast.remove(), 300); 
      });

      container.appendChild(toast);

      setTimeout(() => {
          if (toast.parentElement) {
              toast.classList.add('hide');
              setTimeout(() => toast.remove(), 300);
          }
      }, 3500);
  }

  showLoading(element, message = "") {
    const currentPosition = window.getComputedStyle(element).position;
    if (currentPosition === 'static') {
      element.style.position = 'relative';
    }

    const overlay = document.createElement("div");
    overlay.className = "loading-overlay";
    overlay.innerHTML = `
      <div class="spinner"></div>
      ${message ? `<div class="loading-text"><i class="fas fa-microchip"></i> ${this.escapeHtml(message)}</div>` : ''}
    `;
    element.appendChild(overlay);
    element.loadingOverlay = overlay;
  }

  hideLoading(element) { 
    if (element.loadingOverlay) element.loadingOverlay.remove(); 
  }

  escapeHtml(str) { 
    return String(str ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); 
  }

  formatNumber(n) { 
    const num = Number(n); return Number.isNaN(num) ? String(n) : new Intl.NumberFormat("en-US").format(num); 
  }
}

document.addEventListener("DOMContentLoaded", () => { 
    window.app = new IMSApp(); 
});
