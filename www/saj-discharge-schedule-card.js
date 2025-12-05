/**
 * SAJ Charge/Discharge Schedule Card
 * Visual weekly schedule overview for SAJ H2 Inverter discharge slots
 * Shows discharge time slots in a weekly calendar view
 * 
 * @author stanu74
 * @version 1.0.1
 */

class SajDischargeScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;
    
    console.log('[SAJ Charge/Discharge Schedule Card] Version 1.0.1');
  }

  setConfig(config) {
    if (!config) {
      throw new Error('Invalid configuration');
    }
    
    this._config = {
      title: config.title || 'Charge/Discharge Schedule',
      slotCount: config.slot_count || 7,
      startHour: config.start_hour || 0,
      endHour: config.end_hour || 24,
      hourStep: config.hour_step || 1,
      showPower: config.show_power !== false,
      colorCharge: config.color_charge || 'var(--success-color, #4CAF50)', // Green
      colorDischarge: config.color_discharge || 'var(--error-color, #F44336)', // Red
      colorDisabled: config.color_disabled || 'var(--disabled-text-color)',
      mode: config.mode || 'combined', // 'discharge', 'charge' or 'combined'
      ...config
    };
    
    if (this.shadowRoot && this._hass) {
      this._render();
    }
  }

  set hass(hass) {
    this._hass = hass;
    if (this.shadowRoot && this._config) {
      this._render();
    }
  }

  _render() {
    if (!this._hass || !this._config) return;

    const scheduleData = this._getScheduleData();
    
    this.shadowRoot.innerHTML = `
      <style>${this._getStyles()}</style>
      <ha-card>
        <div class="card-header">${this._config.title}</div>
        <div class="card-content">
          ${this._renderScheduleTable(scheduleData)}
          ${this._config.showPower ? this._renderLegend(scheduleData) : ''}
        </div>
      </ha-card>
    `;
  }

  _getScheduleData() {
    const slots = [];
    const modes = this._config.mode === 'combined' ? ['charge', 'discharge'] : [this._config.mode];
    
    modes.forEach(prefix => {
      console.log(`[Schedule Card] Looking for ${prefix} sensors...`);

      for (let i = 1; i <= this._config.slotCount; i++) {
        // Slot 1 has NO number (e.g. saj_charge_start_time), slots 2-7 have _X
        const slotNum = i === 1 ? '' : `_${i}`;
        
        // Build entity IDs with correct pattern
        const startEntityId = `sensor.saj_${prefix}${slotNum}_start_time`;
        const endEntityId = `sensor.saj_${prefix}${slotNum}_end_time`;
        const powerEntityId = `sensor.saj_${prefix}${slotNum}_power_percent`;
        const dayMaskEntityId = `sensor.saj_${prefix}${slotNum}_day_mask`;
        
        // Get entities from hass
        const startEntity = this._hass.states[startEntityId];
        const endEntity = this._hass.states[endEntityId];
        const powerEntity = this._hass.states[powerEntityId];
        const dayMaskEntity = this._hass.states[dayMaskEntityId];

        // Debug logging
        if (!startEntity) {
          console.warn(`[Schedule Card] Entity not found: ${startEntityId}`);
        }
        if (!endEntity) {
          console.warn(`[Schedule Card] Entity not found: ${endEntityId}`);
        }
        if (!powerEntity) {
          console.warn(`[Schedule Card] Entity not found: ${powerEntityId}`);
        }
        if (!dayMaskEntity) {
          console.warn(`[Schedule Card] Entity not found: ${dayMaskEntityId}`);
        }

        if (startEntity && endEntity) {
          const startTime = startEntity.state;
          const endTime = endEntity.state;
          const power = powerEntity ? parseInt(powerEntity.state) || 0 : 0;
          const dayMask = dayMaskEntity ? parseInt(dayMaskEntity.state) || 127 : 127;

          // Parse time strings (HH:MM)
          const startMatch = startTime.match(/(\d{1,2}):(\d{2})/);
          const endMatch = endTime.match(/(\d{1,2}):(\d{2})/);

          if (startMatch && endMatch) {
            const startHour = parseInt(startMatch[1]);
            const startMinute = parseInt(startMatch[2]);
            const endHour = parseInt(endMatch[1]);
            const endMinute = parseInt(endMatch[2]);

            slots.push({
              type: prefix, // 'charge' or 'discharge'
              slot: i,
              startHour,
              startMinute,
              endHour,
              endMinute,
              power,
              dayMask,
              enabled: power > 0 && dayMask > 0
            });
          } else {
            console.warn(`[Schedule Card] Invalid time format for slot ${i}: ${startTime} - ${endTime}`);
          }
        }
      }
    });
    
    console.log(`[Schedule Card] Found ${slots.length} valid slots:`, slots);
    return slots;
  }

  _renderScheduleTable(slots) {
    const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
    const hours = [];
    
    for (let h = this._config.startHour; h < this._config.endHour; h += this._config.hourStep) {
      hours.push(h);
    }

    // Show debug message if no slots found
    if (slots.length === 0) {
      return `
        <div class="debug-message">
          <h3>⚠️ No slots found</h3>
          <p>Please check if the sensors exist. Expected naming convention:</p>
          <ul>
            <li>sensor.saj_charge_start_time (Slot 1 - no number)</li>
            <li>sensor.saj_charge_2_start_time (Slot 2)</li>
            <li>sensor.saj_discharge_start_time (Slot 1 - no number)</li>
            <li>sensor.saj_discharge_2_start_time (Slot 2)</li>
          </ul>
          <p>Check browser console (F12) for details.</p>
        </div>
      `;
    }

    let html = '<div class="schedule-table">';
    
    // Header row (days)
    html += '<div class="schedule-row header-row">';
    html += '<div class="time-cell header-cell">Time</div>';
    days.forEach(day => {
      html += `<div class="day-cell header-cell">${day}</div>`;
    });
    html += '</div>';

    // Hour rows
    hours.forEach(hour => {
      html += '<div class="schedule-row">';
      html += `<div class="time-cell">${String(hour).padStart(2, '0')}:00</div>`;
      
      days.forEach((day, dayIndex) => {
        const slotsAtTime = this._getSlotsForDayAndHour(slots, dayIndex, hour);
        const cellClass = slotsAtTime.length > 0 ? 'day-cell active' : 'day-cell';
        
        const slotInfo = slotsAtTime.length > 0 
          ? `data-slots="${slotsAtTime.map(s => `${s.type === 'charge' ? '🟢' : '🔴'} Slot ${s.slot}: ${s.power}%`).join(', ')}"` 
          : '';
        
        html += `<div class="${cellClass}" ${slotInfo}>`;
        if (slotsAtTime.length > 0) {
          // Render indicators for all active slots in this hour
          slotsAtTime.forEach(slot => {
            const opacity = 0.3 + (slot.power / 100) * 0.7;
            const color = slot.type === 'charge' ? this._config.colorCharge : this._config.colorDischarge;
            html += `<div class="slot-indicator" style="opacity: ${opacity}; background-color: ${color}"></div>`;
          });
          
          if (this._config.showPower) {
            const label = slotsAtTime.length > 1 ? 'Mix' : `${slotsAtTime[0].power}%`;
            html += `<span class="power-label">${label}</span>`;
          }
        }
        html += '</div>';
      });
      
      html += '</div>';
    });

    html += '</div>';
    return html;
  }

  _getSlotsForDayAndHour(slots, dayIndex, hour) {
    return slots.filter(slot => {
      // Check if day is enabled in bitmask
      const dayEnabled = (slot.dayMask & (1 << dayIndex)) !== 0;
      if (!dayEnabled || !slot.enabled) return false;

      // Check if hour falls within slot time range
      const slotStart = slot.startHour + (slot.startMinute / 60);
      const slotEnd = slot.endHour + (slot.endMinute / 60);
      
      // Handle overnight slots (e.g., 23:00 - 02:00)
      if (slotEnd < slotStart) {
        return hour >= slotStart || hour < slotEnd;
      }
      
      return hour >= slotStart && hour < slotEnd;
    });
  }

  _renderLegend(slots) {
    if (slots.length === 0) return '<div class="legend">No slots configured</div>';

    let html = '<div class="legend">';
    html += '<div class="legend-title">Active Slots:</div>';
    
    // Sort by type then slot number
    const sortedSlots = slots.filter(s => s.enabled).sort((a, b) => {
        if (a.type !== b.type) return a.type.localeCompare(b.type);
        return a.slot - b.slot;
    });

    sortedSlots.forEach(slot => {
      const days = this._getDaysFromMask(slot.dayMask);
      const color = slot.type === 'charge' ? this._config.colorCharge : this._config.colorDischarge;
      const typeLabel = slot.type.charAt(0).toUpperCase() + slot.type.slice(1);
      
      html += `
        <div class="legend-item">
          <div class="legend-indicator" style="background-color: ${color}"></div>
          <span class="legend-text">
            <b>${typeLabel}</b> Slot ${slot.slot}: 
            ${String(slot.startHour).padStart(2, '0')}:${String(slot.startMinute).padStart(2, '0')} - 
            ${String(slot.endHour).padStart(2, '0')}:${String(slot.endMinute).padStart(2, '0')} 
            (${slot.power}%) - ${days}
          </span>
        </div>`;
    });
    
    html += '</div>';
    return html;
  }

  _getDaysFromMask(mask) {
    const dayAbbr = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
    const activeDays = [];
    
    for (let i = 0; i < 7; i++) {
      if (mask & (1 << i)) {
        activeDays.push(dayAbbr[i]);
      }
    }
    
    return activeDays.join(', ') || 'No days';
  }

  _getStyles() {
    return `
      :host {
        display: block;
      }
      
      ha-card {
        padding: 0;
        overflow: hidden;
      }
      
      .card-header {
        font-size: 1.25rem;
        font-weight: 500;
        padding: 16px;
        background-color: var(--primary-color);
        color: var(--text-primary-color);
      }
      
      .card-content {
        padding: 8px;
        overflow-x: hidden;
        overflow-y: auto;
        max-height: 600px; /* Scrollable vertically */
      }
      
      .schedule-table {
        display: table;
        width: 100%;
        border-collapse: collapse;
      }
      
      .schedule-row {
        display: table-row;
      }
      
      .header-row {
        position: sticky;
        top: 0;
        z-index: 10;
        background-color: var(--card-background-color);
      }
      
      .day-cell, .time-cell {
        display: table-cell;
        padding: 4px 2px; /* Reduced from 8px 4px */
        text-align: center;
        border: 1px solid var(--divider-color);
        vertical-align: middle;
        position: relative;
        font-size: 0.85em; /* Slightly smaller font */
        white-space: nowrap;
      }
      
      .header-cell {
        background-color: var(--secondary-background-color);
        font-weight: 600;
        font-size: 0.8em; /* Reduced from 0.85em */
        color: var(--secondary-text-color);
        position: sticky;
        top: 0;
        z-index: 11;
        padding: 4px 2px; /* Reduced from 8px 4px */
      }
      
      .time-cell {
        font-weight: 500;
        background-color: var(--secondary-background-color);
        min-width: 30px; /* Reduced from 60px (50%) */
        position: sticky;
        left: 0;
        z-index: 5;
        box-shadow: 2px 0 4px rgba(0,0,0,0.1);
      }
      
      .header-row .time-cell {
        z-index: 12;
        left: 0;
      }
      
      .day-cell {
        min-width: 40px; /* Reduced from 80px (50%) */
        width: auto;
        height: 20px; /* Reduced from 40px (50%) */
        transition: background-color 0.2s ease;
      }
      
      .day-cell.active {
        background-color: rgba(var(--rgb-primary-color), 0.1);
      }
      
      .day-cell.active:hover {
        background-color: rgba(var(--rgb-primary-color), 0.2);
      }
      
      .day-cell[data-slots]:hover::after {
        content: attr(data-slots);
        position: absolute;
        bottom: 100%;
        left: 50%;
        transform: translateX(-50%);
        background-color: var(--primary-text-color);
        color: var(--text-primary-color);
        padding: 6px 10px;
        border-radius: 4px;
        font-size: 0.85em;
        white-space: nowrap;
        z-index: 100;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        pointer-events: none;
        margin-bottom: 4px;
      }
      
      .slot-indicator {
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        /* background-color is now set inline */
        pointer-events: none;
      }
      
      .power-label {
        position: relative;
        z-index: 1;
        font-size: 0.65em; /* Reduced from 0.75em */
        font-weight: 600;
        color: var(--text-primary-color);
        text-shadow: 0 0 2px rgba(0,0,0,0.5);
      }
      
      .legend {
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid var(--divider-color);
      }
      
      .legend-title {
        font-weight: 600;
        margin-bottom: 8px;
        color: var(--primary-text-color);
      }
      
      .legend-item {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 6px;
        font-size: 0.9em;
      }
      
      .legend-indicator {
        width: 20px;
        height: 12px;
        /* background-color is now set inline */
        border-radius: 2px;
        flex-shrink: 0;
      }
      
      .legend-text {
        color: var(--secondary-text-color);
      }
      
      .debug-message {
        padding: 20px;
        background-color: rgba(var(--rgb-warning-color), 0.1);
        border: 2px solid var(--warning-color);
        border-radius: 8px;
        margin: 16px;
      }
      
      .debug-message h3 {
        margin: 0 0 12px 0;
        color: var(--warning-color);
      }
      
      .debug-message p {
        margin: 8px 0;
        color: var(--primary-text-color);
      }
      
      .debug-message ul {
        margin: 8px 0;
        padding-left: 24px;
        color: var(--secondary-text-color);
      }
      
      .debug-message li {
        margin: 4px 0;
        font-family: monospace;
        font-size: 0.9em;
      }
      
      /* Scrollbar styling for better UX */
      .card-content::-webkit-scrollbar {
        width: 8px;
      }
      
      .card-content::-webkit-scrollbar-track {
        background: var(--secondary-background-color);
        border-radius: 4px;
      }
      
      .card-content::-webkit-scrollbar-thumb {
        background: var(--primary-color);
        border-radius: 4px;
      }
      
      .card-content::-webkit-scrollbar-thumb:hover {
        background: var(--primary-color);
        opacity: 0.8;
      }
      
      @media (max-width: 768px) {
        .card-content {
          padding: 4px;
          max-height: 500px;
        }
        
        .day-cell {
          min-width: 30px; /* Further reduced for mobile */
          padding: 3px 1px;
          font-size: 0.75em;
        }
        
        .time-cell {
          min-width: 25px; /* Further reduced for mobile */
          padding: 3px 1px;
          font-size: 0.75em;
        }
        
        .header-cell {
          font-size: 0.7em;
          padding: 3px 1px;
        }
        
        .power-label {
          font-size: 0.6em;
        }
      }
      
      @media (min-width: 1200px) {
        .card-content {
          max-height: 800px;
        }
        
        .day-cell {
          min-width: 50px; /* 50% of original 100px */
          padding: 5px 3px;
        }
        
        .time-cell {
          min-width: 35px; /* 50% of original 70px */
          padding: 5px 3px;
        }
      }
    `;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define('saj-discharge-schedule-card', SajDischargeScheduleCard);

// Register card for UI editor
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'saj-dis-charge-schedule-card',
  name: 'SAJ Charge/Discharge Schedule Card',
  description: 'Visual weekly schedule overview for discharge slots',
  preview: true,
  documentationURL: 'https://github.com/stanu74/saj-h2-ha-card'
});
