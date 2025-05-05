/**
 * SAJ H2 Charge Card V2
 * Custom card for Home Assistant to control SAJ H2 Inverter charging settings
 * 
 * @author Cline AI Assistant
 * @version 2.0.0
 */

// Define the custom element
class SajH2ChargeCardV2 extends HTMLElement {
  constructor() {
    super();
    this._hass = null;
    this._entities = {
      chargeStart: null,
      chargeEnd: null,
      chargeDayMask: null,
      chargePower: null,
      chargingSwitch: null
    };
    this._theme = 'default';
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
    
    // Store theme if provided
    if (config.theme) {
      this._theme = config.theme;
    }

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
      this._content.innerHTML = `
        <div class="card-error">
          <h2>Entität nicht gefunden</h2>
          <p>Bitte überprüfen Sie die Konfiguration der Karte.</p>
        </div>
      `;
      return;
    }

    // Get current values
    const chargeStart = chargeStartEntity.state;
    const chargeEnd = chargeEndEntity.state;
    const chargeDayMask = parseInt(chargeDayMaskEntity.state) || 0;
    const chargePower = parseInt(chargePowerEntity.state) || 0;
    const chargingEnabled = chargingSwitchEntity.state === 'on';

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
                <input type="time" id="charge-start" value="${chargeStart}" />
              </div>
              <div class="time-input">
                <label>Ende:</label>
                <input type="time" id="charge-end" value="${chargeEnd}" />
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
    const chargeStartInput = this._content.querySelector('#charge-start');
    const chargeEndInput = this._content.querySelector('#charge-end');
    
    chargeStartInput.addEventListener('change', (e) => {
      this._setTimeEntity(this._entities.chargeStart, e.target.value);
    });
    
    chargeEndInput.addEventListener('change', (e) => {
      this._setTimeEntity(this._entities.chargeEnd, e.target.value);
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
      const currentState = this._hass.states[this._entities.chargingSwitch].state;
      const newState = currentState === 'on' ? 'off' : 'on';
      
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
    this._hass.callService('text', 'set_value', {
      entity_id: entityId,
      value: value
    });
  }

  // Set number entity value
  _setNumberEntity(entityId, value) {
    this._hass.callService('number', 'set_value', {
      entity_id: entityId,
      value: value
    });
  }

  // Card styling
  getCardSize() {
    return 4;
  }

  // Load external CSS
  connectedCallback() {
    if (super.connectedCallback) {
      super.connectedCallback();
    }
    
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
customElements.define('saj-h2-charge-card-v2', SajH2ChargeCardV2);

// Add the card to the custom cards list
if (!window.customCards) {
  window.customCards = [];
}

// Add the card to the custom cards list
window.customCards.push({
  type: 'saj-h2-charge-card-v2',
  name: 'SAJ H2 Charge Card V2',
  description: 'Karte zur Steuerung der Ladeeinstellungen für SAJ H2 Wechselrichter (Version 2)'
});
