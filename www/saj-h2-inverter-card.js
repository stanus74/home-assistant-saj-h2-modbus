/**
 * SAJ H2 Inverter Card
 * Custom card for Home Assistant to control SAJ H2 Inverter charging and discharging settings
 * - Uses Shadow DOM for encapsulation.
 * - Supports configuration entity overrides.
 * - Handles pending states via hass object updates.
 * - Protects specific input interactions (time, range) from disruptive re-renders.
 *
 * @author stanu74 
 * @version 1.1.6
 */

class SajH2InverterCard extends HTMLElement {
  static get DEFAULT_ENTITIES() {
    // Default entity IDs (can be overridden in Lovelace config)
    return {
      // Charging entities
      chargeStart: 'text.saj_charge_start_time_time',
      chargeEnd:   'text.saj_charge_end_time_time',
      chargeDayMask: 'number.saj_charge_day_mask_input',
      chargePower: 'number.saj_charge_power_percent_input',
      chargingSwitch: 'switch.saj_charging_control',

      // Discharging entities
      dischargeSlots: [
        { startTime: 'text.saj_discharge1_start_time_time', endTime: 'text.saj_discharge1_end_time_time', power: 'number.saj_discharge1_power_percent_input', dayMask: 'number.saj_discharge1_day_mask_input' },
        { startTime: 'text.saj_discharge2_start_time_time', endTime: 'text.saj_discharge2_end_time_time', power: 'number.saj_discharge2_power_percent_input', dayMask: 'number.saj_discharge2_day_mask_input' },
        { startTime: 'text.saj_discharge3_start_time_time', endTime: 'text.saj_discharge3_end_time_time', power: 'number.saj_discharge3_power_percent_input', dayMask: 'number.saj_discharge3_day_mask_input' },
        { startTime: 'text.saj_discharge4_start_time_time', endTime: 'text.saj_discharge4_end_time_time', power: 'number.saj_discharge4_power_percent_input', dayMask: 'number.saj_discharge4_day_mask_input' },
        { startTime: 'text.saj_discharge5_start_time_time', endTime: 'text.saj_discharge5_end_time_time', power: 'number.saj_discharge5_power_percent_input', dayMask: 'number.saj_discharge5_day_mask_input' },
        { startTime: 'text.saj_discharge6_start_time_time', endTime: 'text.saj_discharge6_end_time_time', power: 'number.saj_discharge6_power_percent_input', dayMask: 'number.saj_discharge6_day_mask_input' },
        { startTime: 'text.saj_discharge7_start_time_time', endTime: 'text.saj_discharge7_end_time_time', power: 'number.saj_discharge7_power_percent_input', dayMask: 'number.saj_discharge7_day_mask_input' }
      ],
      timeEnable:       'number.saj_discharge_time_enable_input',
      dischargingSwitch:'switch.saj_discharging_control'
    };
  }

  constructor() {
    super();

    console.log(`[SAJ H2 Inverter Card] Version: 1.1.6`);
    
    this.attachShadow({ mode: 'open' }); // Attach Shadow DOM
    
    // Initialize properties
    this._entities = JSON.parse(JSON.stringify(SajH2InverterCard.DEFAULT_ENTITIES));
    this._mode = 'both';
    this._hass = null;
    this._debug = false;
    this._sliderTimeouts = {}; // Debouncing-Timeouts speichern
    this._showAllSlots = false; // State für "Show more Slots" Button
  }

  // Called by Lovelace when configuration is set
  setConfig(config) {
    if (!config) {
      throw new Error('Invalid configuration');
    }

    this._mode = config.mode || 'both';
    if (!['charge','discharge','both'].includes(this._mode)) {
      throw new Error(`Invalid mode: ${this._mode}. Must be one of: charge, discharge, both`);
    }

    // Deep merge user-provided entities with defaults
    this._entities = this._deepMerge(
        JSON.parse(JSON.stringify(SajH2InverterCard.DEFAULT_ENTITIES)),
        config.entities || {}
    );

    this._debug = config.debug === true;

    // Trigger initial render if hass is already available
    if (this.shadowRoot && this._hass) {
      this._renderCard();
    }
  }

  // Called by Home Assistant when the state changes
  set hass(hass) {
    if (!hass) return;

    const shouldUpdate = this._shouldUpdate(hass);
    // Check interaction status *before* potential re-render
    const userInteracting = this._isUserInteracting();

    // Update internal state AFTER calculations based on the previous state
    this._hass = hass;

    // Render logic: Render if shadowRoot exists AND (update needed OR initial render)
    // AND user is NOT interacting with protected elements (time, range)
    if (this.shadowRoot && (shouldUpdate || !this.shadowRoot.innerHTML) && !userInteracting) {
        this._renderCard();
    }
  }

  // Check if the user is actively interacting with specific input types
  _isUserInteracting() {
    if (!this.shadowRoot) return false;
    const activeElement = this.shadowRoot.activeElement;
    if (!activeElement) return false;

    // Protect time and range inputs from re-renders while focused
    if (activeElement.tagName === 'INPUT') {
      const type = activeElement.type.toLowerCase();
      if (type === 'time' || type === 'range') {
        return true; // Currently interacting with time or range input
      }
    }
    // Allow rendering for other interactions (buttons, checkboxes, focus elsewhere)
    return false;
  }

  // Determine if a re-render is needed based on relevant entity state changes
  _shouldUpdate(newHass) {
    if (!this._hass) return true; // Always update if old state doesn't exist

    // --- Gather all relevant entity IDs based on current config ---
    const relevantEntityIds = [];
    if (this._mode !== 'discharge') {
        relevantEntityIds.push(
            this._entities.chargeStart, this._entities.chargeEnd,
            this._entities.chargeDayMask, this._entities.chargePower,
            this._entities.chargingSwitch // Crucial switch
        );
    }
    if (this._mode !== 'charge') {
        relevantEntityIds.push(
            this._entities.timeEnable,
            this._entities.dischargingSwitch, // Crucial switch
            // Use flatMap to handle potentially complex/nested slot structures safely
            ...(this._entities.dischargeSlots || []).flatMap(slot => slot ? [slot.startTime, slot.endTime, slot.power, slot.dayMask] : [])
        );
    }
    // Remove duplicates and filter out any null/undefined values
    const uniqueIds = [...new Set(relevantEntityIds)].filter(Boolean);

    // --- Check for changes in any relevant entity ---
    for (const id of uniqueIds) {
        const oldState = this._hass.states[id];
        const newState = newHass.states[id];

        // Check if state object itself is different (covers new/removed entities)
        if (oldState !== newState) {
            // Specifically check if pending_write status changed
            if (oldState?.attributes?.pending_write !== newState?.attributes?.pending_write) {
                return true;
            }
             // Check if the state value itself changed
             if (oldState?.state !== newState?.state) {
                 return true;
             }
             // If entity just appeared/disappeared update is needed
             if(!oldState || !newState) return true;
        }
    }

    // No relevant changes detected that require a re-render
    return false;
  }

  // Main render function, updates the Shadow DOM
  _renderCard() {
    if (!this._hass || !this.shadowRoot) return; // Guard clauses

    // Final check before manipulating DOM
    if (this._isUserInteracting()) {
         return;
    }

    // --- Prepare Content ---
    let cardContent = '';
    let hasError = false;

    // Render Charging Section
    if (this._mode !== 'discharge') {
      const chargeResult = this._renderChargingSection();
      if (chargeResult.error) hasError = true;
      cardContent += chargeResult.html;
    }

    // Render Discharging Section
    if (this._mode !== 'charge') {
      const dischargeResult = this._renderDischargingSection();
       if (dischargeResult.error) hasError = true;
      cardContent += dischargeResult.html;
    }

    // Add general error if specific sections failed silently
     if (hasError && !cardContent.includes('card-error') && !cardContent.includes('ha-alert')) {
         cardContent = `<ha-alert alert-type="error">Required entities missing. Please check card configuration and ensure entities exist in Home Assistant.</ha-alert>` + cardContent;
     }

    // --- Render to Shadow DOM ---
    // Store current focus and selection range (if any) to restore it later
    const activeElement = this.shadowRoot.activeElement;
    const activeElementId = activeElement?.id;
    const selectionStart = activeElement?.selectionStart;
    const selectionEnd = activeElement?.selectionEnd;

    this.shadowRoot.innerHTML = `
      <style>
        ${this._getStyles()}
      </style>
      <ha-card>
        <div class="card-content">
          ${cardContent}
        </div>
      </ha-card>
    `;

    // Restore focus and selection if an element had focus before re-render
    if (activeElementId) {
        const elementToRestoreFocus = this.shadowRoot.getElementById(activeElementId);
        if (elementToRestoreFocus) {
            elementToRestoreFocus.focus();
            // Restore selection range for text/time inputs if applicable
            if (selectionStart !== undefined && selectionEnd !== undefined && typeof elementToRestoreFocus.setSelectionRange === 'function') {
                try {
                    elementToRestoreFocus.setSelectionRange(selectionStart, selectionEnd);
                } catch (e) {
                    // Ignore errors (e.g., element type doesn't support selection range)
                }
            }
        }
    }

    // Add event listeners after the DOM is updated
    // Use requestAnimationFrame to ensure DOM is fully painted before adding listeners/setting styles
    requestAnimationFrame(() => {
        this._addEventListeners();
        this._updateSliderStyles(); // Update slider track fills after render
    });
  }

  // Render the charging section HTML
  _renderChargingSection() {
    const s = this._entities;
    const es = this._hass.states;
    const start = es[s.chargeStart], end = es[s.chargeEnd], mask = es[s.chargeDayMask], power = es[s.chargePower], sw = es[s.chargingSwitch];

    if (!start || !end || !mask || !power || !sw) {
      const missing = [
          !start && s.chargeStart, !end && s.chargeEnd, !mask && s.chargeDayMask,
          !power && s.chargePower, !sw && s.chargingSwitch
      ].filter(Boolean).join(', ');
      return { html: `<div class="card-error"><h2>Charging Entities Missing</h2><p>Check: ${missing || 'configuration'}</p></div>`, error: true };
    }

    const chargeStart = start.state;
    const chargeEnd = end.state;
    const chargeDayMask = parseInt(mask.state) || 0;
    const chargePower = parseInt(power.state) || 0;
    const chargingEnabled = sw.state === 'on';
    const pendingWrite = sw.attributes?.pending_write === true;

    // Only disable inputs during Modbus transfer (pending write), NOT when disabled
    const inputsDisabled = pendingWrite;

    const html = `
      <div class="section charging-section">
        <div class="section-header">Charging Settings (Version 1.1.6)</div>
        ${!chargingEnabled && !pendingWrite ? '<div class="hint-message">ℹ️ Charging is currently disabled. Settings can be edited and will be applied when enabled.</div>' : ''}
        ${pendingWrite ? '<div class="hint-message">🕓 Settings pending confirmation via Modbus...</div>' : ''}
        <div class="subsection">
          <div class="subsection-header">Charging Time & Power</div>
          <div class="time-power-container">
            <div class="time-power-row">
              ${this._renderTimeSelects('charge', chargeStart, chargeEnd, chargePower, inputsDisabled)}
            </div>
            <div class="slider-container">
              <input type="range" id="charge-power" class="power-slider" min="0" max="25" step="1" value="${chargePower}" ${inputsDisabled ? 'disabled' : ''} />
            </div>
          </div>
        </div>
        <div class="subsection">
          <div class="subsection-header">Charging Days</div>
          <div class="days-selection">
            ${this._renderDayCheckboxes('charge', chargeDayMask, inputsDisabled)}
          </div>
        </div>
        <div class="subsection">
          <div class="subsection-header">Charging Control</div>
          ${this._renderStatusButton(chargingEnabled, pendingWrite, 'charging')}
        </div>
      </div>`;
      return { html: html, error: false };
  }

  // Render the discharging section HTML
  _renderDischargingSection() {
    const switchEntityId = this._entities.dischargingSwitch;
    const timeEnableEntityId = this._entities.timeEnable;
    const sw = this._hass.states[switchEntityId];
    const timeEnableEntity = this._hass.states[timeEnableEntityId];

    if (!sw || !timeEnableEntity) {
        const missing = [!sw && switchEntityId, !timeEnableEntity && timeEnableEntityId].filter(Boolean).join(', ');
       return { html: `<div class="card-error"><h2>Discharging Entities Missing</h2><p>Check: ${missing || 'configuration'}</p></div>`, error: true };
    }

    const dischargingEnabled = sw.state === 'on';
    const pendingWrite = sw.attributes?.pending_write === true;
    const timeEnableValue = parseInt(timeEnableEntity.state) || 0;
    
    // Only disable slot settings during Modbus transfer (pending write), NOT when disabled
    const inputsDisabled = pendingWrite;

    // Collect slot configuration and errors
    let slotErrors = [];
    const slots = (this._entities.dischargeSlots || []).map((slotConfig, i) => {
      if (!slotConfig) return { index: i, valid: false };

      const sStart = this._hass.states[slotConfig.startTime];
      const sEnd = this._hass.states[slotConfig.endTime];
      const sPower = this._hass.states[slotConfig.power];
      const sMask = this._hass.states[slotConfig.dayMask];
      const valid = sStart && sEnd && sPower && sMask;

      if (!valid) {
          const missing = [!sStart && slotConfig.startTime, !sEnd && slotConfig.endTime, !sPower && slotConfig.power, !sMask && slotConfig.dayMask].filter(Boolean).join(', ');
          slotErrors.push(`Slot ${i+1}: ${missing || 'invalid config'}`);
      }

      return {
        index: i, valid, enabled: (timeEnableValue & (1 << i)) !== 0,
        startTime: valid ? sStart.state : '00:00', endTime: valid ? sEnd.state : '00:00',
        power: valid ? parseInt(sPower.state) || 0 : 0, dayMask: valid ? parseInt(sMask.state) || 0 : 0,
        config: slotConfig
      };
    });

    // Slot 1 immer anzeigen, Slots 2-7 nur wenn _showAllSlots true ist
    const visibleSlots = this._showAllSlots ? slots : slots.slice(0, 1);
    const hiddenSlotsCount = slots.length - visibleSlots.length;
    
    let slotHtml = visibleSlots.map(s => this._renderDischargeSlot(s, inputsDisabled)).join('');
    if (slotErrors.length > 0) {
        slotHtml = `<ha-alert alert-type="warning" title="Discharge Slot Entity Errors">${slotErrors.join('; ')}</ha-alert>` + slotHtml;
    }

    const showMoreButton = hiddenSlotsCount > 0 ? `
      <button id="show-more-slots" class="show-more-button">
        Show ${hiddenSlotsCount} more Slot${hiddenSlotsCount > 1 ? 's' : ''}
      </button>` : '';
    
    const showLessButton = this._showAllSlots ? `
      <button id="show-less-slots" class="show-more-button">
        Show less Slots
      </button>` : '';

    const html = `
      <div class="section discharging-section">
        <div class="section-header">Discharging Settings</div>
        ${!dischargingEnabled && !pendingWrite ? '<div class="hint-message">ℹ️ Discharging is currently disabled. Settings can be edited and will be applied when enabled.</div>' : ''}
        ${pendingWrite ? '<div class="hint-message">🕓 Settings pending confirmation via Modbus...</div>' : ''}
        <div class="subsection">
          <div class="subsection-header">Discharge Time Slots</div>
          <div class="discharge-slots">
            ${slotHtml}
          </div>
          ${showMoreButton}
          ${showLessButton}
        </div>
        <div class="subsection">
          <div class="subsection-header">Discharging Control</div>
          ${this._renderStatusButton(dischargingEnabled, pendingWrite, 'discharging')}
        </div>
      </div>`;
      return { html: html, error: false };
  }

  // Render a single discharge slot HTML
  _renderDischargeSlot(slot, parentPendingWrite = false) {
    if (!slot.valid) {
        return `<div class="discharge-slot invalid">Slot ${slot.index+1}: Configuration Error</div>`;
    }
    // Check if the timeEnable entity itself is pending
    const timeEnablePending = this._hass.states[this._entities.timeEnable]?.attributes?.pending_write === true;
    // Controls inside the slot are disabled ONLY during Modbus transfer (pending write)
    // They remain enabled even if slot is not enabled - user can configure while disabled
    const contentDisabled = parentPendingWrite || timeEnablePending;
    const checkboxDisabled = parentPendingWrite || timeEnablePending;

    return `
      <div class="discharge-slot ${slot.enabled ? 'enabled' : 'disabled'} ${parentPendingWrite || timeEnablePending ? 'pending' : ''}">
        <div class="slot-header">
          <label class="slot-checkbox">
            <input type="checkbox" id="slot-${slot.index}-enabled" ${slot.enabled ? 'checked' : ''} ${checkboxDisabled ? 'disabled' : ''} />
            <span>Slot ${slot.index+1}</span>
          </label>
        </div>
        <div class="slot-content ${slot.enabled ? 'visible' : 'hidden'}">
          <div class="time-power-container">
            <div class="time-power-row">
              ${this._renderTimeSelects(`slot-${slot.index}`, slot.startTime, slot.endTime, slot.power, contentDisabled)}
            </div>
            <div class="slider-container">
              <input type="range" id="slot-${slot.index}-power" class="power-slider" min="0" max="100" step="1" value="${slot.power}" ${contentDisabled ? 'disabled' : ''} />
            </div>
          </div>
          <div class="days-select">
            ${this._renderDayCheckboxes(`slot-${slot.index}`, slot.dayMask, contentDisabled)}
          </div>
        </div>
      </div>`;
  }

  // Debounce Slider-Änderungen (verzögert Service-Call)
  // Verhindert zu viele Modbus-Calls bei schnellen Slider-Bewegungen
  _debouncedSliderChange(sliderId, entityId, value, delay = 800) {
    // Alten Timer löschen, falls noch aktiv
    if (this._sliderTimeouts[sliderId]) {
      clearTimeout(this._sliderTimeouts[sliderId]);
      if (this._debug) {
        console.log(`[saj-h2-inverter-card] Debounce Timer abgebrochen für ${sliderId}`);
      }
    }

    // Neuen Timer starten
    this._sliderTimeouts[sliderId] = setTimeout(() => {
      if (this._debug) {
        console.log(`[saj-h2-inverter-card] Debounce abgelaufen: Sende ${sliderId} = ${value}`);
      }
      this._setEntityValue(entityId, parseInt(value, 10), 'number');
      delete this._sliderTimeouts[sliderId];
    }, delay);

    if (this._debug) {
      console.log(`[saj-h2-inverter-card] Debounce Timer gestartet für ${sliderId} (${delay}ms)`);
    }
  }

  // Render the time input elements
  _renderTimeSelects(prefix, startTime, endTime, power = null, disabled = false) {
     // Ensure times are valid HH:MM format or default
     const validStartTime = /^([01]\d|2[0-3]):([0-5]\d)$/.test(startTime) ? startTime : '00:00';
     const validEndTime = /^([01]\d|2[0-3]):([0-5]\d)$/.test(endTime) ? endTime : '00:00';

     return `
    <div class="time-box-container">
      <div class="time-box start-time">
        <div class="time-box-label">Start</div>
        <div class="time-input-container">
          <input type="time" id="${prefix}-start-time" value="${validStartTime}" step="300" class="time-input" ${disabled ? 'disabled' : ''} />
        </div>
      </div>
      <div class="time-box end-time">
        <div class="time-box-label">End</div>
        <div class="time-input-container">
          <input type="time" id="${prefix}-end-time" value="${validEndTime}" step="300" class="time-input" ${disabled ? 'disabled' : ''} />
        </div>
      </div>
      <div class="time-box power-time">
        <div class="time-box-label">Power</div>
        <div class="power-placeholder">
          ${power !== null ? `<span class="power-value">${power}%</span>` : ''}
        </div>
      </div>
    </div>`;
  }

  // Render day selection checkboxes
  _renderDayCheckboxes(prefix, mask, disabled = false) {
    const days = this._getDaysFromMask(mask);
    return ['Mo','Tu','We','Th','Fr','Sa','Su'].map((dayAbbr, i) => `
      <label class="day-checkbox ${disabled ? 'disabled' : ''}">
        <input type="checkbox" id="${prefix}-day-${dayAbbr.toLowerCase()}" data-day-index="${i}" ${days[['monday','tuesday','wednesday','thursday','friday','saturday','sunday'][i]] ? 'checked' : ''} ${disabled ? 'disabled' : ''} />
        <span>${dayAbbr}</span>
      </label>`).join('');
  }

  // Render the main status button (Charge/Discharge enable/disable)
  // This version relies *only* on isPending from the hass state.
  _renderStatusButton(isEnabled, isPending, type) {
    const typeCapitalized = type.charAt(0).toUpperCase() + type.slice(1);
    // Button text indicates the action clicking will take
    const actionText = isEnabled ? `Disable ${typeCapitalized}` : `Enable ${typeCapitalized}`;
    // Button HTML: Disable it when pending.
    const button = `<button id="${type}-toggle" class="control-button ${isEnabled ? 'active' : ''}" ${isPending ? 'disabled' : ''}>${actionText}</button>`;

    // Status Display HTML: Show specific "Wait..." message ONLY when pending.
    let statusDisplayHtml;
    if (isPending) {
        statusDisplayHtml = `
            <div class="status-display">
                <div class="wait-message">Wait for Modbus Transfer</div>
            </div>`;
    } else {
        const statusText = isEnabled ? `${typeCapitalized} active` : `${typeCapitalized} inactive`;
        statusDisplayHtml = `
            <div class="status-display">
                Status: <span class="status-value ${isEnabled ? 'active' : 'inactive'}">${statusText}</span>
            </div>`;
    }
    // Combine button and status display
    return `${button}${statusDisplayHtml}`;
  }

  // Add all event listeners after rendering
  _addEventListeners() {
    if (!this.shadowRoot) return;
    if (this._mode !== 'discharge') this._addChargingEventListeners();
    if (this._mode !== 'charge') this._addDischargingEventListeners();
  }

  // Add listeners for the charging section
  _addChargingEventListeners() {
    const q = sel => this.shadowRoot.querySelector(sel);
    const chargeSection = q('.charging-section');
    if (!chargeSection) return;

    // Charge Toggle Button
    const toggle = q('#charging-toggle');
    if (toggle && !toggle.hasAttribute('data-listener-added')) {
      toggle.setAttribute('data-listener-added', 'true');
      toggle.addEventListener('click', () => {
        const entityId = this._entities.chargingSwitch;
        const currentState = this._hass.states[entityId]?.state;
        if (!currentState) {
            console.error(`[saj-h2-inverter-card] Entity ${entityId} not found in hass state.`);
            return;
        }
        const newState = currentState === 'on' ? 'off' : 'on';
        // NO OPTIMISTIC UI UPDATE HERE - just call the service
        this._hass.callService('switch', `turn_${newState}`, { entity_id: entityId });
        // UI update relies entirely on receiving new hass state with pending_write
      });
    }

    // Charge Time Inputs
    this._setupTimeListeners('charge', this._entities.chargeStart, this._entities.chargeEnd);

    // Charge Power Slider - MIT DEBOUNCING
    const slider = q('#charge-power');
    if (slider && !slider.hasAttribute('data-listener-added')) {
        slider.setAttribute('data-listener-added', 'true');
        const powerValueDisplay = chargeSection.querySelector('.power-value');
        slider.addEventListener('input', e => { // Update display and style immediately on input
             const value = e.target.value;
             if (powerValueDisplay) powerValueDisplay.textContent = `${value}%`;
             this._updateSingleSliderStyle(slider); // Update track fill
        });
         slider.addEventListener('change', e => { // Send value to HA with debouncing (release)
             this._debouncedSliderChange('charge-power', this._entities.chargePower, e.target.value, 800);
         });
    }

    // Charge Day Checkboxes
    this._setupDayListeners('charge', this._entities.chargeDayMask);
  }

  // Add listeners for the discharging section
  _addDischargingEventListeners() {
    const q = sel => this.shadowRoot.querySelector(sel);
    const dischargeSection = q('.discharging-section');
    if (!dischargeSection) return;

    // "Show more Slots" Button
    const showMoreBtn = q('#show-more-slots');
    if (showMoreBtn && !showMoreBtn.hasAttribute('data-listener-added')) {
      showMoreBtn.setAttribute('data-listener-added', 'true');
      showMoreBtn.addEventListener('click', () => {
        this._showAllSlots = true;
        this._renderCard();
      });
    }

    // "Show less Slots" Button
    const showLessBtn = q('#show-less-slots');
    if (showLessBtn && !showLessBtn.hasAttribute('data-listener-added')) {
      showLessBtn.setAttribute('data-listener-added', 'true');
      showLessBtn.addEventListener('click', () => {
        this._showAllSlots = false;
        this._renderCard();
      });
    }

    // Discharge Toggle Button
    const toggle = q('#discharging-toggle');
    if (toggle && !toggle.hasAttribute('data-listener-added')) {
      toggle.setAttribute('data-listener-added', 'true');
      toggle.addEventListener('click', () => {
        const entityId = this._entities.dischargingSwitch;
        const currentState = this._hass.states[entityId]?.state;
        if (!currentState) {
             console.error(`[saj-h2-inverter-card] Entity ${entityId} not found in hass state.`);
            return;
        }
        const newState = currentState === 'on' ? 'off' : 'on';
        
        // First turn on/off the switch
        this._hass.callService('switch', `turn_${newState}`, { entity_id: entityId });
        
        // When turning ON, send values for all enabled slots
        if (newState === 'on') {
          this._sendEnabledSlotValues();
        }
      });
    }

    // Discharge Slot Listeners
    const timeEnableEntityId = this._entities.timeEnable;
    (this._entities.dischargeSlots || []).forEach((slotConfig, i) => {
      if (!slotConfig) return;
      const slotElement = q(`#slot-${i}-enabled`)?.closest('.discharge-slot');
      if (!slotElement) return;

      // Slot Enable Checkbox
      const chk = q(`#slot-${i}-enabled`);
      if (chk && !chk.hasAttribute('data-listener-added')) {
        chk.setAttribute('data-listener-added', 'true');
        chk.addEventListener('change', () => {
            const timeEnableState = this._hass.states[timeEnableEntityId];
            if (!timeEnableState) {
                console.error(`[saj-h2-inverter-card] Entity ${timeEnableEntityId} not found in hass state.`);
                // Maybe disable checkbox if state is missing? Or revert?
                chk.checked = !chk.checked; // Simple revert for now
                return;
            }
            const currentMask = parseInt(timeEnableState.state || '0');
            const bit = 1 << i;
            const newMask = chk.checked ? (currentMask | bit) : (currentMask & ~bit);
            this._setEntityValue(timeEnableEntityId, newMask, 'number');
            // Optimistically toggle content visibility for responsiveness
            const content = slotElement.querySelector('.slot-content');
            if (content) {
                content.classList.toggle('hidden', !chk.checked);
                content.classList.toggle('visible', chk.checked);
            }
        });
      }

      // Slot Time Inputs
      this._setupTimeListeners(`slot-${i}`, slotConfig.startTime, slotConfig.endTime);

      // Slot Power Slider - MIT DEBOUNCING
      const slider = q(`#slot-${i}-power`);
      if (slider && !slider.hasAttribute('data-listener-added')) {
        slider.setAttribute('data-listener-added', 'true');
        const powerValueDisplay = slotElement.querySelector('.power-value');
        slider.addEventListener('input', e => { // Update display and style immediately on input
          const value = e.target.value;
          if (powerValueDisplay) powerValueDisplay.textContent = `${value}%`;
          this._updateSingleSliderStyle(slider); // Update track fill
        });
        slider.addEventListener('change', e => { // Send value to HA with debouncing (release)
          this._debouncedSliderChange(`slot-${i}-power`, slotConfig.power, e.target.value, 800);
        });
      }

      // Slot Day Checkboxes
      this._setupDayListeners(`slot-${i}`, slotConfig.dayMask);
    });
  }

  // Send values for enabled slots to ensure proper configuration
  _sendEnabledSlotValues() {
    try {
      // Get the currently enabled slots
      const timeEnableEntityId = this._entities.timeEnable;
      const timeEnableState = this._hass.states[timeEnableEntityId];
      
      if (!timeEnableState) {
        console.warn(`[saj-h2-inverter-card] Entity ${timeEnableEntityId} not found in hass state.`);
        return;
      }
      
      const enabledMask = parseInt(timeEnableState.state || '0');
      if (!enabledMask) {
        console.info('[saj-h2-inverter-card] No discharge slots enabled. Nothing to send.');
        return;
      }
      
      console.info(`[saj-h2-inverter-card] Sending values for enabled discharge slots: ${enabledMask.toString(2)}`);
      
      // For each enabled slot, send its current configuration values
      (this._entities.dischargeSlots || []).forEach((slotConfig, i) => {
        // Check if this slot bit is set in the mask
        if ((enabledMask & (1 << i)) && slotConfig) {
          const slotNumber = i + 1;
          
          // Get current values for this slot
          const startTime = this._hass.states[slotConfig.startTime]?.state || '00:00';
          const endTime = this._hass.states[slotConfig.endTime]?.state || '00:00';
          const power = parseInt(this._hass.states[slotConfig.power]?.state || '5');
          const dayMask = parseInt(this._hass.states[slotConfig.dayMask]?.state || '127'); // Default all days
          
          console.info(`[saj-h2-inverter-card] Slot ${slotNumber}: sending ${startTime}-${endTime}, ${power}%, mask=${dayMask}`);
          
          // Send values to Home Assistant
          if (slotConfig.startTime) {
            this._setEntityValue(slotConfig.startTime, startTime, 'text');
          }
          if (slotConfig.endTime) {
            this._setEntityValue(slotConfig.endTime, endTime, 'text');
          }
          if (slotConfig.power) {
            this._setEntityValue(slotConfig.power, power, 'number');
          }
          if (slotConfig.dayMask) {
            this._setEntityValue(slotConfig.dayMask, dayMask, 'number');
          }
        }
      });
    } catch (error) {
      console.error('[saj-h2-inverter-card] Error in _sendEnabledSlotValues:', error);
    }
  }

  // Helper to setup time input listeners
  _setupTimeListeners(prefix, startEntity, endEntity) {
    if (!this.shadowRoot) return;
    ['start', 'end'].forEach(type => {
      const input = this.shadowRoot.querySelector(`#${prefix}-${type}-time`);
      const entityId = type === 'start' ? startEntity : endEntity;
      if (input && !input.hasAttribute('data-listener-added')) {
        input.setAttribute('data-listener-added', 'true');
        input.addEventListener('change', e => {
            if (/^([01]\d|2[0-3]):([0-5]\d)$/.test(e.target.value)) {
                 this._setEntityValue(entityId, e.target.value, 'text');
            } else {
                console.warn(`[saj-h2-inverter-card] Invalid time format entered for ${entityId}: ${e.target.value}. Reverting.`);
                const prevState = this._hass.states[entityId]?.state;
                 if (prevState && /^([01]\d|2[0-3]):([0-5]\d)$/.test(prevState)) {
                     e.target.value = prevState;
                 } else {
                     e.target.value = '00:00'; // Fallback
                 }
            }
        });
      }
    });
  }

  // Helper to setup day checkbox listeners using event delegation
  _setupDayListeners(prefix, maskEntity) {
     if (!this.shadowRoot || !maskEntity) return;
     const container = this.shadowRoot.querySelector(`#${prefix}-day-mo`)?.closest('.days-selection, .days-select');

     if (container && !container.hasAttribute(`data-day-listener-${prefix}`)) {
        container.setAttribute(`data-day-listener-${prefix}`, 'true');
        container.addEventListener('change', (event) => {
            if (event.target.matches(`input[type="checkbox"][id^="${prefix}-day-"]`)) {
                let newMask = 0;
                container.querySelectorAll(`input[type="checkbox"][id^="${prefix}-day-"]`).forEach(cb => {
                    if (cb.checked) {
                        const dayIndex = parseInt(cb.dataset.dayIndex, 10);
                        if (!isNaN(dayIndex)) newMask |= (1 << dayIndex);
                    }
                });
                this._setEntityValue(maskEntity, newMask, 'number');
            }
        });
        // Mark initial checkboxes as having listener handled by container
        container.querySelectorAll(`input[type="checkbox"][id^="${prefix}-day-"]`).forEach(chk => {
            chk.setAttribute('data-listener-handled', 'true');
        });
     } else if (container) {
         // Ensure any dynamically added checkboxes are also marked (less likely scenario)
         container.querySelectorAll(`input[type="checkbox"][id^="${prefix}-day-"]:not([data-listener-handled])`).forEach(chk => {
             chk.setAttribute('data-listener-handled', 'true');
         });
     }
  }

  // Call HA service to set entity value
  _setEntityValue(entityId, value, domain = 'text') {
    if (!this._hass || !entityId) {
        console.error(`[saj-h2-inverter-card] Attempted to set invalid entity ID: ${entityId}`);
        return;
    }
    const service = domain === 'switch' ? `turn_${value}` : 'set_value';
    const serviceData = domain === 'switch' ? { entity_id: entityId } : { entity_id: entityId, value: value };

    this._hass.callService(domain, service, serviceData)
      .then(() => {
        this._debug && console.log(`[saj-h2-inverter-card] Successfully called ${domain}.${service} for ${entityId}`);
      })
      .catch(err => {
        console.error(`[saj-h2-inverter-card] Error calling ${domain}.${service} for ${entityId}:`, err);
        this.dispatchEvent(new CustomEvent('hass-notification', {
            detail: { message: `Error setting ${entityId}: ${err.message}` },
            bubbles: true, composed: true
        }));
      });
  }

  // Calculate bitmask from day selection object
  _calculateDaymask(days) {
    const dayKeys = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    return dayKeys.reduce((sum, day, i) => sum + ((days && days[day]) ? (1 << i) : 0), 0);
  }

  // Get day selection object from bitmask
  _getDaysFromMask(mask) {
    const days = {};
    ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'].forEach((day, i) => {
      days[day] = (mask & (1 << i)) !== 0;
    });
    return days;
  }

  // Update slider track fill based on current value
  _updateSingleSliderStyle(slider) {
      if (!slider) return;
      const min = parseFloat(slider.min) || 0;
      const max = parseFloat(slider.max) || 100;
      const value = parseFloat(slider.value) || 0;
      const percentage = max === min ? 0 : ((value - min) / (max - min)) * 100;
      slider.style.setProperty('--value-percent', `${percentage}%`);
  }

  // Update styles for all sliders after rendering
  _updateSliderStyles() {
      if (!this.shadowRoot) return;
      this.shadowRoot.querySelectorAll('.power-slider').forEach(slider => {
          this._updateSingleSliderStyle(slider);
      });
  }

  // Calculate the card size for Lovelace layout
  getCardSize() {
    let size = 1;
    if (this._mode !== 'discharge') size += 3;
    if (this._mode !== 'charge') {
      size += 2;
      try {
        if (this._hass && this._entities.timeEnable && this._hass.states[this._entities.timeEnable]) {
            const timeEnableValue = parseInt(this._hass.states[this._entities.timeEnable].state || '0');
            const enabledSlots = (this._entities.dischargeSlots || []).filter((slot, i) => slot && (timeEnableValue & (1 << i)) !== 0).length;
            size += Math.ceil(enabledSlots / 1.5);
        } else if (this._entities.dischargeSlots) {
             size += Math.ceil((this._entities.dischargeSlots || []).length / 2);
        }
      } catch (e) { size += 3; console.warn("[saj-h2-inverter-card] Error calculating card size:", e); }
    }
    return Math.max(1, Math.min(15, size));
  }

  // Runs when the element is added to the DOM
  connectedCallback() {
     if (this.shadowRoot && this._hass && !this.shadowRoot.innerHTML) {
        this._renderCard();
     }
  }

  // Helper function for deep merging configuration objects
  _deepMerge(target, source) {
      const isObject = (obj) => obj && typeof obj === 'object' && !Array.isArray(obj);
      if (!isObject(target) || !isObject(source)) {
          return source !== null && source !== undefined ? source : target;
      }
      const output = { ...target };
      Object.keys(source).forEach(key => {
          const targetValue = output[key];
          const sourceValue = source[key];
          if (Array.isArray(targetValue) && Array.isArray(sourceValue)) {
              output[key] = sourceValue; // Array replacement
          } else if (isObject(targetValue) && isObject(sourceValue)) {
              output[key] = this._deepMerge(targetValue, sourceValue);
          } else {
              output[key] = sourceValue;
          }
      });
       Object.keys(target).forEach(key => { // Ensure keys only in target are kept
            if (source[key] === undefined) {
                output[key] = target[key];
            }
       });
      return output;
  }

  // Return the CSS styles
  _getStyles() {
    return `
      :host {
        display: block;
        --slider-track-color: var(--input-fill-color, #F0F0F0);
        --slider-thumb-color: var(--paper-slider-knob-color, var(--primary-color));
        --slider-active-color: var(--paper-slider-active-color, var(--primary-color));
        --error-color-rgb: var(--rgb-error-color, 211, 47, 47);
        --warning-color-rgb: var(--rgb-warning-color, 255, 152, 0);
        --primary-color-rgb: var(--rgb-primary-color, 33, 150, 243);
        --disabled-text-color-rgb: var(--rgb-disabled-text-color, 180, 180, 180);
      }
      ha-card {
        height: 100%; display: flex; flex-direction: column;
        justify-content: space-between; overflow: hidden;
      }
      .card-content { padding: 16px; flex-grow: 1; }
      .card-error {
        background-color: var(--error-color); color: var(--text-primary-color-on-error, white);
        padding: 12px; border-radius: 8px; margin-bottom: 16px;
      }
      .card-error h2 { margin: 0 0 8px 0; font-size: 1.1em; color: var(--text-primary-color-on-error, white); }
      .card-error p { margin: 0; font-size: 0.9em; word-break: break-all; color: var(--text-primary-color-on-error, white); }
      ha-alert { display: block; margin-bottom: 16px; }
      ha-alert[alert-type="warning"] { --alert-warning-color: var(--warning-color); }
      ha-alert[alert-type="error"] { --alert-error-color: var(--error-color); }
      .section { margin-bottom: 24px; }
      .charging-section, .discharging-section {
        border: 1px solid var(--divider-color); border-radius: 12px;
        padding: 16px; background-color: var(--card-background-color);
      }
      .section-header {
        font-size: 1.25rem; font-weight: 500; margin: -16px -16px 16px -16px;
        padding: 12px 16px; color: var(--primary-text-color);
        border-bottom: 1px solid var(--divider-color);
        background-color: var(--app-header-background-color, var(--secondary-background-color));
        border-radius: 12px 12px 0 0; letter-spacing: 0.5px;
      }
      .subsection { margin-bottom: 20px; }
      .subsection:last-child { margin-bottom: 0; }
      .subsection-header { font-size: 1.1rem; font-weight: 500; margin-bottom: 12px; color: var(--primary-text-color); }

      /* Time and Power Row */
      .time-box-container {
        display: flex; align-items: stretch; justify-content: space-between;
        width: 100%; background-color: var(--secondary-background-color);
        border-radius: 12px; padding: 16px; margin-bottom: 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05); gap: 16px; box-sizing: border-box;
      }
      .time-box { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 80px; }
      .power-time { flex: 0 1 auto; min-width: 70px; justify-content: center; }
      .time-box-label {
        font-size: 0.9em; font-weight: 500; margin-bottom: 6px;
        color: var(--secondary-text-color); text-transform: uppercase;
        letter-spacing: 0.5px; white-space: nowrap;
      }
      .time-input-container {
        display: flex; align-items: center; border: 1px solid var(--input-ink-color, var(--divider-color));
        border-radius: 8px; padding: 0 6px; background-color: var(--input-fill-color, var,--card-background-color));
        width: 100%; min-height: 40px; box-sizing: border-box; transition: background-color 0.2s ease, border-color 0.2s ease;
      }
      .time-input-container:hover:not(:has(input:disabled)) { border-color: var(--input-hover-ink-color, var(--primary-color)); }
      .time-input {
        flex-grow: 1; padding: 8px 4px; border: none; background-color: transparent; color: var(--primary-text-color);
        font-size: 1.1em; font-weight: 500; text-align: center; min-width: 70px; outline: none; color-scheme: light dark;
      }
      .time-input:disabled { color: var(--disabled-text-color); cursor: not-allowed; }
      .time-input-container:has(input:disabled) {
        background-color: var(--input-disabled-fill-color, rgba(var(--disabled-text-color-rgb), 0.1));
        border-color: var(--input-disabled-ink-color, var(--divider-color)); cursor: not-allowed;
      }
      .power-placeholder { display: flex; align-items: center; justify-content: center; width: 100%; min-height: 40px; box-sizing: border-box; }
      .power-value {
        display: inline-flex; align-items: center; justify-content: center; padding: 8px 12px;
        border: 1px solid var(--input-ink-color, var,--divider-color)); border-radius: 8px;
        background-color: var(--input-fill-color, var,--card-background-color)); font-size: 1.1em; font-weight: 500;
        color: var(--primary-text-color); min-width: 60px; min-height: 40px; box-sizing: border-box; text-align: center;
        transition: background-color 0.2s ease, border-color 0.2s ease;
      }
      .time-box.power-time:has(input:disabled) .power-value, /* If parent time box input is disabled */
      .time-power-row:has(input.power-slider:disabled) .power-value /* If sibling slider is disabled */
       {
        background-color: var(--input-disabled-fill-color, rgba(var(--disabled-text-color-rgb), 0.1));
        border-color: var(--input-disabled-ink-color, var,--divider-color)); color: var(--disabled-text-color);
      }

      /* Days Selection */
      .days-selection, .days-select { display: flex; flex-wrap: nowrap; gap: 6px; margin-bottom: 12px; justify-content: space-between; }
      .day-checkbox { display: flex; align-items: center; gap: 4px; cursor: pointer; padding: 4px 6px; border-radius: 8px; transition: background-color 0.2s ease; flex: 1; min-width: 0; }
      .day-checkbox:not(.disabled):hover { background-color: rgba(var(--primary-color-rgb), 0.1); }
      .day-checkbox span { font-size: 0.9em; user-select: none; white-space: nowrap; }
      .day-checkbox input[type="checkbox"] { width: 16px; height: 16px; margin-right: 2px; cursor: pointer; accent-color: var(--primary-color); flex-shrink: 0; }
      .day-checkbox input[type="checkbox"]:disabled { cursor: not-allowed; accent-color: var(--disabled-text-color); opacity: 0.7; }
      .day-checkbox.disabled { cursor: not-allowed; color: var(--disabled-text-color); opacity: 0.7; }

      /* Slider */
      .time-power-container { display: flex; flex-direction: column; margin-bottom: 12px; }
      .time-power-row { display: flex; align-items: center; justify-content: flex-start; gap: 16px; margin-bottom: 12px; }
      .slider-container { width: 100%; padding: 0 8px; box-sizing: border-box; margin-top: 8px;}
      .power-slider {
        width: 100%; height: 8px; cursor: pointer; appearance: none;
        /* Track fill using CSS variable set by JS */
        background: linear-gradient(to right, var(--slider-active-color) 0%, var(--slider-active-color) var(--value-percent, 0%), var(--slider-track-color) var(--value-percent, 0%), var(--slider-track-color) 100%);
        border-radius: 4px; outline: none; transition: background .1s ease-in-out; margin: 8px 0;
      }
      .power-slider::-webkit-slider-thumb { appearance: none; width: 20px; height: 20px; background: var(--slider-thumb-color); border-radius: 50%; cursor: pointer; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
      .power-slider::-moz-range-thumb { width: 20px; height: 20px; background: var(--slider-thumb-color); border-radius: 50%; cursor: pointer; border: none; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
      .power-slider:disabled { background: var(--input-disabled-fill-color, #E0E0E0); cursor: not-allowed; opacity: 0.6; }
      .power-slider:disabled::-webkit-slider-thumb { background: var(--disabled-text-color); cursor: not-allowed; box-shadow: none; }
      .power-slider:disabled::-moz-range-thumb { background: var(--disabled-text-color); cursor: not-allowed; box-shadow: none; }

      /* Control Button & Status */
      .control-button {
        width: 100%; padding: 14px; font-size: 1.1rem; border-radius: 8px; border: none;
        background-color: var(--primary-color); color: var(--text-primary-color-on-primary, white); font-weight: 500;
        cursor: pointer; margin-bottom: 10px; transition: all 0.2s ease; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      }
      .control-button:hover:not(:disabled) { filter: brightness(110%); box-shadow: 0 2px 6px rgba(0,0,0,0.15); }
      .control-button:active:not(:disabled) { transform: scale(0.98); }
      .control-button.active { background-color: var(--error-color); }
      .control-button.active:hover:not(:disabled) { background-color: var(--error-color); filter: brightness(110%); }
      .control-button:disabled {
          background-color: var(--disabled-text-color); color: var(--text-primary-color-on-disabled, #FAFAFA);
          cursor: not-allowed; box-shadow: none; opacity: 0.7;
      }
      .status-display {
          text-align: center; font-size: 0.95em; color: var(--secondary-text-color); min-height: 30px;
          display: flex; flex-direction: column; justify-content: center; align-items: center;
      }
      .status-value { font-weight: 500; transition: color 0.3s ease; }
      .status-value.active { color: var(--success-color, MediumSeaGreen); }
      .status-value.inactive { color: var(--error-color, Tomato); }
      .wait-message { /* Specific style for the wait message */
        font-weight: 500; color: var(--warning-color); padding: 6px 0 0 0;
        text-align: center; font-size: 0.9em; animation: pulse 1.5s infinite ease-in-out;
      }
      @keyframes pulse { 0%, 100% { opacity: 0.7; } 50% { opacity: 1; } }

      /* Discharge Slots */
      .discharge-slot {
        padding: 16px; border-radius: 8px; background-color: var(--secondary-background-color);
        border-left: 5px solid var(--disabled-text-color); margin-bottom: 12px; width: 100%;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08); transition: border-left-color 0.3s ease, opacity 0.3s ease; box-sizing: border-box;
      }
      .discharge-slot.enabled { border-left-color: var(--primary-color); }
      .discharge-slot.invalid { border-left-color: var(--error-color); background-color: rgba(var(--error-color-rgb), 0.05); color: var(--error-color); font-weight: 500; padding: 10px 16px; }
      .discharge-slot.pending { opacity: 0.7; /* Dim slot when parent or timeEnable is pending */ }
      .discharge-slot.pending .slot-content > * { pointer-events: none; opacity: 0.7; } /* Disable content interaction */
      .slot-header { cursor: default; /* Header not clickable per se */ padding-bottom: 8px; }
      .slot-checkbox { display: flex; align-items: center; gap: 8px; cursor: pointer; width: fit-content;} /* Label is clickable */
      .slot-checkbox input[type="checkbox"] { width: 18px; height: 18px; accent-color: var(--primary-color); cursor: pointer; }
      .slot-checkbox input[type="checkbox"]:disabled { cursor: not-allowed; accent-color: var(--disabled-text-color); opacity: 0.7;}
      .slot-checkbox span { font-size: 1.1em; font-weight: 500; user-select: none; }
      .slot-content { margin-top: 12px; overflow: hidden; transition: max-height 0.3s ease-in-out, opacity 0.3s ease-in-out, margin-top 0.3s ease-in-out; max-height: 0; opacity: 0; }
      .slot-content.visible { max-height: 500px; opacity: 1; }
      .slot-content.hidden { margin-top: 0; }

      /* Show More Slots Button */
      .show-more-button {
        width: 100%; padding: 12px; font-size: 1rem; border-radius: 8px;
        border: 1px solid var(--divider-color); background-color: var(--card-background-color);
        color: var(--primary-text-color); font-weight: 500; cursor: pointer;
        margin-top: 12px; transition: all 0.2s ease;
      }
      .show-more-button:hover {
        background-color: var(--secondary-background-color);
        border-color: var(--primary-color);
      }
      .show-more-button:active {
        transform: scale(0.98);
      }

      /* Responsive adjustments */
      @media (max-width: 450px) {
        .card-content { padding: 12px; }
        .section-header { font-size: 1.15rem; padding: 10px 12px;}
        .subsection-header { font-size: 1.05rem; }
        .time-box-container { flex-direction: column; align-items: stretch; padding: 12px; gap: 12px; }
        .time-box { width: 100%; align-items: center; }
        .power-time { align-items: center; }
        .time-input-container, .power-placeholder, .power-value { min-height: 38px; }
        .power-value { padding: 6px 10px; }
        .time-input { font-size: 1.05em; }
        .days-selection, .days-select { gap: 4px; }
        .day-checkbox { padding: 3px 4px; gap: 3px; }
        .day-checkbox span { font-size: 0.85em; }
        .day-checkbox input[type="checkbox"] { width: 14px; height: 14px; }
        .discharge-slot { padding: 12px; width: 100%; }
        .slot-checkbox span { font-size: 1.05em; }
        .control-button { font-size: 1rem; padding: 12px; }
      }
    `;
  }
}

// Register the custom element
customElements.define('saj-h2-inverter-card', SajH2InverterCard);

// Add card to custom card list for UI editor (run only once)
if (!window.sajH2CardDefined) {
    window.customCards = window.customCards || [];
    window.customCards.push({
      type: 'saj-h2-inverter-card',
      name: 'SAJ H2 Inverter Card',
      description: 'Card for controlling SAJ H2 inverter charge/discharge settings.',
      preview: true,
      documentationURL: 'https://github.com/stanu74/saj-h2-ha-card'
    });
    window.sajH2CardDefined = true;
}
