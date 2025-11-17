/**
 * SAJ Discharge Schedule Card
 * Visual weekly schedule overview for SAJ H2 Inverter discharge slots
 * Shows discharge time slots in a weekly calendar view
 * 
 * @author stanu74
 * @version 1.0.0
 */

class SajDischargeScheduleCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._config = null;
    this._hass = null;
    
    console.log('[SAJ Discharge Schedule Card] Version 1.0.0');
  }

  setConfig(config) {
    if (!config) {
      throw new Error('Invalid configuration');
    }
    
    this._config = {
      title: config.title || 'Discharge Schedule',
      slotCount: config.slot_count || 7,
      startHour: config.start_hour || 0,
      endHour: config.end_hour || 24,
      hourStep: config.hour_step || 1,
      showPower: config.show_power !== false,
      colorEnabled: config.color_enabled || 'var(--primary-color)',
      colorDisabled: config.color_disabled || 'var(--disabled-text-color)',
      mode: config.mode || 'discharge', // 'discharge' or 'charge'
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
    const mode = this._config.mode;
    const prefix = mode === 'charge' ? 'charge' : 'discharge';
    const slots = [];

    for (let i = 1; i <= this._config.slotCount; i++) {
      const slotNum = i === 1 ? '' : `_${i}`;
      const startEntity = this._hass.states[`sensor.saj_${prefix}${slotNum}_start_time`];
      const endEntity = this._hass.states[`sensor.saj_${prefix}${slotNum}_end_time`];
      const powerEntity = this._hass.states[`sensor.saj_${prefix}${i}_power_percent`];
      const dayMaskEntity = this._hass.states[`sensor.saj_${prefix}${i}_day_mask`];

      if (startEntity && endEntity) {
        const startTime = startEntity.state;
        const endTime = endEntity.state;
        const power = powerEntity ? parseInt(powerEntity.state) : 0;
        const dayMask = dayMaskEntity ? parseInt(dayMaskEntity.state) : 127;

        // Parse time strings (HH:MM)
        const startMatch = startTime.match(/(\d{1,2}):(\d{2})/);
        const endMatch = endTime.match(/(\d{1,2}):(\d{2})/);

        if (startMatch && endMatch) {
          const startHour = parseInt(startMatch[1]);
          const startMinute = parseInt(startMatch[2]);
          const endHour = parseInt(endMatch[1]);
          const endMinute = parseInt(endMatch[2]);

          slots.push({
            slot: i,
            startHour,
            startMinute,
            endHour,
            endMinute,
            power,
            dayMask,
            enabled: power > 0 && dayMask > 0
          });
        }
      }
    }

    return slots;
  }

  _renderScheduleTable(slots) {
    const days = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'];
    const hours = [];
    
    for (let h = this._config.startHour; h < this._config.endHour; h += this._config.hourStep) {
      hours.push(h);
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
          ? `data-slots="${slotsAtTime.map(s => `Slot ${s.slot}: ${s.power}%`).join(', ')}"` 
          : '';
        
        html += `<div class="${cellClass}" ${slotInfo}>`;
        if (slotsAtTime.length > 0) {
          const maxPower = Math.max(...slotsAtTime.map(s => s.power));
          const opacity = 0.3 + (maxPower / 100) * 0.7;
          html += `<div class="slot-indicator" style="opacity: ${opacity}"></div>`;
          if (this._config.showPower && slotsAtTime.length === 1) {
            html += `<span class="power-label">${slotsAtTime[0].power}%</span>`;
          } else if (this._config.showPower && slotsAtTime.length > 1) {
            html += `<span class="power-label">×${slotsAtTime.length}</span>`;
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
    
    slots.filter(s => s.enabled).forEach(slot => {
      const days = this._getDaysFromMask(slot.dayMask);
      html += `
        <div class="legend-item">
          <div class="legend-indicator"></div>
          <span class="legend-text">
            Slot ${slot.slot}: 
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
        padding: 8px 4px;
        text-align: center;
        border: 1px solid var(--divider-color);
        vertical-align: middle;
        position: relative;
        font-size: 0.9em;
        white-space: nowrap;
      }
      
      .header-cell {
        background-color: var(--secondary-background-color);
        font-weight: 600;
        font-size: 0.85em;
        color: var(--secondary-text-color);
        position: sticky;
        top: 0;
        z-index: 11;
        padding: 8px 4px;
      }
      
      .time-cell {
        font-weight: 500;
        background-color: var(--secondary-background-color);
        min-width: 60px;
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
        min-width: 80px;
        width: auto;
        height: 40px;
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
        background-color: var(--primary-color);
        pointer-events: none;
      }
      
      .power-label {
        position: relative;
        z-index: 1;
        font-size: 0.75em;
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
        background-color: var(--primary-color);
        border-radius: 2px;
        flex-shrink: 0;
      }
      
      .legend-text {
        color: var(--secondary-text-color);
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
          min-width: 60px;
          padding: 6px 2px;
          font-size: 0.8em;
        }
        
        .time-cell {
          min-width: 50px;
          padding: 6px 2px;
          font-size: 0.8em;
        }
        
        .header-cell {
          font-size: 0.75em;
          padding: 6px 2px;
        }
        
        .power-label {
          font-size: 0.7em;
        }
      }
      
      @media (min-width: 1200px) {
        .card-content {
          max-height: 800px;
        }
        
        .day-cell {
          min-width: 100px;
          padding: 10px 6px;
        }
        
        .time-cell {
          min-width: 70px;
          padding: 10px 6px;
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
  type: 'saj-discharge-schedule-card',
  name: 'SAJ Discharge Schedule Card',
  description: 'Visual weekly schedule overview for discharge slots',
  preview: true,
  documentationURL: 'https://github.com/stanu74/saj-h2-ha-card'
});
