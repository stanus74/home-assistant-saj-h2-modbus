/**
 * SAJ H2 Charge Card V3
 * Custom card for Home Assistant to control SAJ H2 Inverter charging settings
 * 
 * @author Cline AI Assistant
 * @version 3.0.1
 */

class SajH2ChargeCardV3 extends HTMLElement {
  constructor() {
    super();
    this._entities = {
      chargeStart: null,
      chargeEnd: null,
      chargeDayMask: null,
      chargePower: null,
      chargingSwitch: null
    };
    this._hass = null;
    this._debug = false; // Set to true to enable debug logging
  }

  // Card configuration
  setConfig(config) {
    // Validate required entities
    if (!config.charge_start_entity) {
      throw new Error('You need to define a charge_start_entity');
    }
    if (!config.charge_end_entity) {
      throw new Error('You need to define a charge_end_entity');
    }
    if (!config.charge_day_mask_entity) {
      throw new Error('You need to define a charge_day_mask_entity');
    }
    if (!config.charge_power_entity) {
      throw new Error('You need to define a charge_power_entity');
    }
    if (!config.charging_switch_entity) {
      throw new Error('You need to define a charging_switch_entity');
    }

    // Store entity IDs
    this._entities.chargeStart = config.charge_start_entity;
    this._entities.chargeEnd = config.charge_end_entity;
    this._entities.chargeDayMask = config.charge_day_mask_entity;
    this._entities.chargePower = config.charge_power_entity;
    this._entities.chargingSwitch = config.charging_switch_entity;
    
    this._initCard();
  }

  _initCard() {
    if (this._content) {
      this.removeChild(this._content);
    }
    
    // Create the card content
    this._content = document.createElement('div');
    this._content.className = 'saj-h2-charge-card';
    this.appendChild(this._content);
    
    if (this._hass) {
      this._renderCard();
    }
  }

  // Handle updates when Home Assistant state changes
  set hass(hass) {
    this._hass = hass;
    this._renderCard();
  }

  // Render the card
  _renderCard() {
    if (!this._hass || !this._entities.chargeStart) {
      return;
    }

    // Get entity states
    const chargeStartEntity = this._hass.states[this._entities.chargeStart];
    const chargeEndEntity = this._hass.states[this._entities.chargeEnd];
    const chargeDayMaskEntity = this._hass.states[this._entities.chargeDayMask];
    const chargePowerEntity = this._hass.states[this._entities.chargePower];
    const chargingSwitchEntity = this._hass.states[this._entities.chargingSwitch];

    // Check if entities exist
    if (!chargeStartEntity || !chargeEndEntity || !chargeDayMaskEntity || 
        !chargePowerEntity || !chargingSwitchEntity) {
      
    // Log which entities are missing for debugging
    if (this._debug) {
      console.log('SAJ H2 Charge Card: Missing entities:');
      if (!chargeStartEntity) console.log('- Missing: ' + this._entities.chargeStart);
      if (!chargeEndEntity) console.log('- Missing: ' + this._entities.chargeEnd);
      if (!chargeDayMaskEntity) console.log('- Missing: ' + this._entities.chargeDayMask);
      if (!chargePowerEntity) console.log('- Missing: ' + this._entities.chargePower);
      if (!chargingSwitchEntity) console.log('- Missing: ' + this._entities.chargingSwitch);
    }
      
      this._content.innerHTML = `
        <div class="card-error">
          <h2>Entität nicht gefunden</h2>
          <p>Bitte überprüfen Sie die Konfiguration der Karte.</p>
          <p>Fehlende Entität: ${!chargeStartEntity ? this._entities.chargeStart : 
                               !chargeEndEntity ? this._entities.chargeEnd :
                               !chargeDayMaskEntity ? this._entities.chargeDayMask :
                               !chargePowerEntity ? this._entities.chargePower :
                               !chargingSwitchEntity ? this._entities.chargingSwitch : 'Unbekannt'}</p>
        </div>
      `;
      return;
    }

    // Get current values
    const chargeStart = chargeStartEntity.state;
    const chargeEnd = chargeEndEntity.state;
    const chargeDayMask = parseInt(chargeDayMaskEntity.state) || 0;
    const chargePower = parseInt(chargePowerEntity.state) || 0;
    
    // Handle switch state, ignoring attributes
    const chargingEnabled = chargingSwitchEntity.state === 'on';
    
    // Log entity states for debugging
    if (this._debug) {
      console.log('SAJ H2 Charge Card: Entity states:');
      console.log('- ' + this._entities.chargeStart + ': ' + chargeStart);
      console.log('- ' + this._entities.chargeEnd + ': ' + chargeEnd);
      console.log('- ' + this._entities.chargeDayMask + ': ' + chargeDayMask);
      console.log('- ' + this._entities.chargePower + ': ' + chargePower);
      console.log('- ' + this._entities.chargingSwitch + ': ' + chargingSwitchEntity.state);
      if (chargingSwitchEntity.attributes) {
        console.log('- ' + this._entities.chargingSwitch + ' attributes:', chargingSwitchEntity.attributes);
      }
    }

    // Get days from mask
    const days = this._getDaysFromMask(chargeDayMask);

    // Render the card content
    this._content.innerHTML = `
      <ha-card>
        <div class="card-content">
          <div class="section">
            <div class="section-header">Ladezeit</div>
            <div class="time-inputs">
              <div class="time-input">
                <label>Start:</label>
                <div class="time-selectors">
                  <select id="charge-start-hour" class="time-select">
                    ${this._generateHourOptions(chargeStart)}
                  </select>
                  <span>:</span>
                  <select id="charge-start-minute" class="time-select">
                    ${this._generateMinuteOptions(chargeStart)}
                  </select>
                </div>
              </div>
              <div class="time-input">
                <label>Ende:</label>
                <div class="time-selectors">
                  <select id="charge-end-hour" class="time-select">
                    ${this._generateHourOptions(chargeEnd)}
                  </select>
                  <span>:</span>
                  <select id="charge-end-minute" class="time-select">
                    ${this._generateMinuteOptions(chargeEnd)}
                  </select>
                </div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-header">Ladeleistung</div>
            <div class="power-slider">
              <div class="slider-container">
                <input type="range" id="charge-power" min="0" max="25" step="1" value="${chargePower}" />
                <div class="slider-value">${chargePower}%</div>
              </div>
            </div>
          </div>

          <div class="section">
            <div class="section-header">Ladetage</div>
            <div class="days-selection">
              <label class="day-checkbox">
                <input type="checkbox" id="day-monday" ${days.monday ? 'checked' : ''} />
                <span>Mo</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-tuesday" ${days.tuesday ? 'checked' : ''} />
                <span>Di</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-wednesday" ${days.wednesday ? 'checked' : ''} />
                <span>Mi</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-thursday" ${days.thursday ? 'checked' : ''} />
                <span>Do</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-friday" ${days.friday ? 'checked' : ''} />
                <span>Fr</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-saturday" ${days.saturday ? 'checked' : ''} />
                <span>Sa</span>
              </label>
              <label class="day-checkbox">
                <input type="checkbox" id="day-sunday" ${days.sunday ? 'checked' : ''} />
                <span>So</span>
              </label>
            </div>
            <div class="daymask-value">
              Daymask-Wert: ${chargeDayMask}
            </div>
          </div>

          <div class="section">
            <div class="section-header">Ladesteuerung</div>
            <button class="charge-toggle-button ${chargingEnabled ? 'active' : ''}" id="charge-toggle">
              ${chargingEnabled ? 'Laden deaktivieren' : 'Laden aktivieren'}
            </button>
            <div class="charge-status">
              Status: <span class="${chargingEnabled ? 'active' : 'inactive'}">${chargingEnabled ? 'Aktiv' : 'Inaktiv'}</span>
            </div>
          </div>
        </div>
      </ha-card>
    `;

    // Add event listeners
    this._addEventListeners();
  }

  // Add event listeners to the card elements
  _addEventListeners() {
    // Time inputs
    const chargeStartHour = this._content.querySelector('#charge-start-hour');
    const chargeStartMinute = this._content.querySelector('#charge-start-minute');
    const chargeEndHour = this._content.querySelector('#charge-end-hour');
    const chargeEndMinute = this._content.querySelector('#charge-end-minute');
    
    // Add event listeners for start time
    chargeStartHour.addEventListener('change', () => {
      const hour = chargeStartHour.value.padStart(2, '0');
      const minute = chargeStartMinute.value.padStart(2, '0');
      this._setTimeEntity(this._entities.chargeStart, `${hour}:${minute}`);
    });
    
    chargeStartMinute.addEventListener('change', () => {
      const hour = chargeStartHour.value.padStart(2, '0');
      const minute = chargeStartMinute.value.padStart(2, '0');
      this._setTimeEntity(this._entities.chargeStart, `${hour}:${minute}`);
    });
    
    // Add event listeners for end time
    chargeEndHour.addEventListener('change', () => {
      const hour = chargeEndHour.value.padStart(2, '0');
      const minute = chargeEndMinute.value.padStart(2, '0');
      this._setTimeEntity(this._entities.chargeEnd, `${hour}:${minute}`);
    });
    
    chargeEndMinute.addEventListener('change', () => {
      const hour = chargeEndHour.value.padStart(2, '0');
      const minute = chargeEndMinute.value.padStart(2, '0');
      this._setTimeEntity(this._entities.chargeEnd, `${hour}:${minute}`);
    });

    // Power slider
    const chargePowerSlider = this._content.querySelector('#charge-power');
    chargePowerSlider.addEventListener('input', (e) => {
      const value = parseInt(e.target.value);
      this._content.querySelector('.slider-value').textContent = `${value}%`;
    });
    
    chargePowerSlider.addEventListener('change', (e) => {
      const value = parseInt(e.target.value);
      this._setNumberEntity(this._entities.chargePower, value);
    });

    // Day checkboxes
    const dayCheckboxes = this._content.querySelectorAll('.day-checkbox input');
    dayCheckboxes.forEach(checkbox => {
      checkbox.addEventListener('change', () => {
        const days = {
          monday: this._content.querySelector('#day-monday').checked,
          tuesday: this._content.querySelector('#day-tuesday').checked,
          wednesday: this._content.querySelector('#day-wednesday').checked,
          thursday: this._content.querySelector('#day-thursday').checked,
          friday: this._content.querySelector('#day-friday').checked,
          saturday: this._content.querySelector('#day-saturday').checked,
          sunday: this._content.querySelector('#day-sunday').checked
        };
        
        const mask = this._calculateDaymask(days);
        this._content.querySelector('.daymask-value').textContent = `Daymask-Wert: ${mask}`;
        this._setNumberEntity(this._entities.chargeDayMask, mask);
      });
    });

    // Charge toggle button
    const chargeToggleButton = this._content.querySelector('#charge-toggle');
    chargeToggleButton.addEventListener('click', () => {
      // Get the switch entity
      const switchEntity = this._hass.states[this._entities.chargingSwitch];
      
      // Check if the entity exists
      if (!switchEntity) {
        console.error('SAJ H2 Charge Card: Switch entity not found: ' + this._entities.chargingSwitch);
        return;
      }
      
      // Get the current state, ignoring attributes
      const currentState = switchEntity.state;
      const newState = currentState === 'on' ? 'off' : 'on';
      
      if (this._debug) {
        console.log('SAJ H2 Charge Card: Toggling switch from ' + currentState + ' to ' + newState);
      }
      
      // Call the service to toggle the switch
      this._hass.callService('switch', 'turn_' + newState, {
        entity_id: this._entities.chargingSwitch
      });
    });
  }

  // Calculate daymask from selected days
  _calculateDaymask(days) {
    let mask = 0;
    if (days.monday) mask += 1;
    if (days.tuesday) mask += 2;
    if (days.wednesday) mask += 4;
    if (days.thursday) mask += 8;
    if (days.friday) mask += 16;
    if (days.saturday) mask += 32;
    if (days.sunday) mask += 64;
    return mask;
  }

  // Generate hour options (0-23)
  _generateHourOptions(timeString) {
    const hour = this._getHourFromTimeString(timeString);
    let options = '';
    
    for (let i = 0; i < 24; i++) {
      const selected = i === hour ? 'selected' : '';
      options += `<option value="${i}" ${selected}>${i}</option>`;
    }
    
    return options;
  }
  
  // Generate minute options (0-59)
  _generateMinuteOptions(timeString) {
    const minute = this._getMinuteFromTimeString(timeString);
    let options = '';
    
    for (let i = 0; i < 60; i++) {
      const selected = i === minute ? 'selected' : '';
      options += `<option value="${i}" ${selected}>${i}</option>`;
    }
    
    return options;
  }
  
  // Get hour from time string (format: HH:MM)
  _getHourFromTimeString(timeString) {
    if (!timeString || timeString.indexOf(':') === -1) {
      return 0;
    }
    
    return parseInt(timeString.split(':')[0]) || 0;
  }
  
  // Get minute from time string (format: HH:MM)
  _getMinuteFromTimeString(timeString) {
    if (!timeString || timeString.indexOf(':') === -1) {
      return 0;
    }
    
    return parseInt(timeString.split(':')[1]) || 0;
  }

  // Get days from daymask
  _getDaysFromMask(mask) {
    return {
      monday: (mask & 1) !== 0,
      tuesday: (mask & 2) !== 0,
      wednesday: (mask & 4) !== 0,
      thursday: (mask & 8) !== 0,
      friday: (mask & 16) !== 0,
      saturday: (mask & 32) !== 0,
      sunday: (mask & 64) !== 0
    };
  }

  // Set time entity value
  _setTimeEntity(entityId, value) {
    try {
      this._hass.callService('text', 'set_value', {
        entity_id: entityId,
        value: value
      });
      if (this._debug) {
        console.log(`SAJ H2 Charge Card: Set ${entityId} to ${value}`);
      }
    } catch (error) {
      console.error(`SAJ H2 Charge Card: Error setting ${entityId} to ${value}:`, error);
    }
  }

  // Set number entity value
  _setNumberEntity(entityId, value) {
    try {
      this._hass.callService('number', 'set_value', {
        entity_id: entityId,
        value: value
      });
      if (this._debug) {
        console.log(`SAJ H2 Charge Card: Set ${entityId} to ${value}`);
      }
    } catch (error) {
      console.error(`SAJ H2 Charge Card: Error setting ${entityId} to ${value}:`, error);
    }
  }

  // Card styling
  getCardSize() {
    return 4;
  }

  // Load external CSS
  connectedCallback() {
    super.connectedCallback && super.connectedCallback();
    
    // Load the CSS file
    if (!document.getElementById('saj-h2-charge-card-styles')) {
      const style = document.createElement('link');
      style.id = 'saj-h2-charge-card-styles';
      style.rel = 'stylesheet';
      style.href = '/local/saj-h2-charge-card/saj-h2-charge-card.css';
      document.head.appendChild(style);
    }
  }
}

// Register the element with a new name
customElements.define('saj-h2-charge-card-v3', SajH2ChargeCardV3);

// Add the card to the custom cards list
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'saj-h2-charge-card-v3',
  name: 'SAJ H2 Charge Card V3',
  description: 'Karte zur Steuerung der Ladeeinstellungen für SAJ H2 Wechselrichter (Version 3)'
});
