async function loadConfig(){ const r = await fetch('/api/config'); return r.json(); }

function el(tag, attrs={}, ...children){
  const n = document.createElement(tag);
  for (const [k,v] of Object.entries(attrs||{})){
    if (k==='class') n.className = v;
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v);
    else if (k==='html') n.innerHTML = v;
    else n.setAttribute(k, v);
  }
  for (const c of children){ if (c==null) continue; n.appendChild(typeof c==='string'?document.createTextNode(c):c); }
  return n;
}
function get(obj, path){ return path.reduce((o,k)=> (o&&o[k]!=null)?o[k]:undefined, obj); }
function set(obj, path, val){
  let o = obj;
  for (let i=0;i<path.length-1;i++){ const k = path[i]; if (!o[k] || typeof o[k]!=='object') o[k] = {}; o = o[k]; }
  o[path[path.length-1]] = val;
}

function renderBoolean(name, path, state, spec){
  const id = `bool_${name}_${Math.random().toString(36).slice(2,7)}`;
  const cb = el('input',{type:'checkbox', class:'checkbox',
    onchange:e=> set(state, path, e.target.checked)});
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, cb)
  );
}

// Boolean with Value - special handling for left_starting_zone
function renderBooleanWithValue(name, path, state, spec){
  const id = `boolwv_${name}_${Math.random().toString(36).slice(2,7)}`;
  const cb = el('input',{
    type:'checkbox', 
    class:'checkbox',
    onchange:e=> set(state, path, e.target.checked)
  });
  
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, cb)
  );
} 

function renderString(name, path, state, spec){
  const id = `str_${name}_${Math.random().toString(36).slice(2,7)}`;
  const inp = el('input',{type:'text', id, placeholder:name, value:'', oninput:e=> set(state, path, e.target.value)});
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, inp)
  );
}

// Typed Integer with increment/decrement buttons
function renderNumber(name, path, state, isFloat){
  const id = `num_${name}_${Math.random().toString(36).slice(2,7)}`;
  let v = 0;
  
  const container = el('div', {class: 'mobile-number-input'});
  const label = el('label', {for: id}, name);
  const controls = el('div', {class: 'number-controls'});
  
  const input = el('input',{
    id,
    type: 'number', 
    value: '0',
    oninput: e => {
      v = isFloat ? parseFloat(e.target.value) || 0 : parseInt(e.target.value) || 0;
      set(state, path, isFloat? v : Math.round(v));
    }
  });
  
  const dec = el('button',{
    class:'btn btn-red', 
    onclick:()=>{ 
      v = isFloat ? v - 1 : v - 1;
      input.value = isFloat ? v : Math.round(v);
      set(state, path, isFloat? v : Math.round(v));
    }
  }, '–');
  
  const inc = el('button',{
    class:'btn btn-green', 
    onclick:()=>{ 
      v = isFloat ? v + 1 : v + 1;
      input.value = isFloat ? v : Math.round(v);
      set(state, path, isFloat? v : Math.round(v));
    }
  }, '+');
  
  controls.appendChild(dec);
  controls.appendChild(input);
  controls.appendChild(inc);
  
  container.appendChild(label);
  container.appendChild(controls);
  
  return container;
}

function renderSingleChoice(name, path, state, options){
  const id = `sc_${name}_${Math.random().toString(36).slice(2,7)}`;
  const sel = el('select',{id, onchange:e=> set(state, path, e.target.value)});
  sel.appendChild(el('option',{value:''}, 'Select…'));
  (options||[]).forEach(o=> sel.appendChild(el('option',{value:o}, o)));
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, sel)
  );
}

function renderSingleChoiceWithValue(name, path, state, options, values){
  const id = `scwv_${name}_${Math.random().toString(36).slice(2,7)}`;
  const sel = el('select',{
    id,
    onchange:e=> {
      const selectedIndex = e.target.selectedIndex;
      if (selectedIndex > 0 && values && values[selectedIndex - 1] !== undefined) {
        set(state, path, options[selectedIndex - 1]);
      } else {
        set(state, path, e.target.value);
      }
    }
  });
  
  sel.appendChild(el('option',{value:''}, 'Select…'));
  
  (options||[]).forEach((o, index) => {
    const optionValue = values && values[index] !== undefined ? values[index] : o;
    sel.appendChild(el('option',{value:o}, `${o} (${optionValue} pts)`));
  });
  
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, sel)
  );
}

function renderMultipleChoiceWithValue(name, path, state, options, values){
  const box = el('div',{class:'form-controls'});
  const current = new Set(get(state, path) || []);
  
  (options||[]).forEach((opt, index) => {
    const value = values && values[index] !== undefined ? values[index] : opt;
    const id = `mcwv_${name}_${opt}_${Math.random().toString(36).slice(2,7)}`;
    const cb = el('input',{
      type:'checkbox', 
      id, 
      value: value,
      checked: current.has(value),
      onchange:e=>{
        if (e.target.checked) current.add(value); 
        else current.delete(value);
        set(state, path, Array.from(current));
      }
    });
    box.appendChild(el('label', {for:id, class:'badge'}, cb, ' ', opt));
  });
  
  return el('div',{class:'form-row'}, el('label',{}, name), box);
}

function renderMultipleChoice(name, path, state, options){
  const box = el('div',{class:'form-controls'});
  const current = new Set(get(state, path) || []);
  (options||[]).forEach(opt=>{
    const id = `mc_${name}_${opt}_${Math.random().toString(36).slice(2,7)}`;
    const cb = el('input',{
      type:'checkbox', 
      id, 
      checked: current.has(opt),
      onchange:e=>{
        if (e.target.checked) current.add(opt); else current.delete(opt);
        set(state, path, Array.from(current));
      }
    });
    box.appendChild(el('label', {for:id, class:'badge'}, cb, ' ', opt));
  });
  return el('div',{class:'form-row'}, el('label',{}, name), box);
}


function renderTimer(name, path, state){
  const id = `timer_${name}_${Math.random().toString(36).slice(2,7)}`;
  let t = 0; let interval = null;
  const disp = el('span',{class:'counter'}, '0.00');
  const fmt = (x)=> (x/100).toFixed(2);
  const update = ()=> disp.textContent = fmt(t);
  const start = ()=> { if (interval) return; interval = setInterval(()=>{ t+=1; update(); }, 10); };
  const stop = ()=> { if (interval) { clearInterval(interval); interval=null; } };
  const reset = ()=> { t=0; update(); set(state, path, 0); };
  const startBtn = el('button',{class:'btn btn-green', onclick:()=>{ start(); }}, 'Start');
  const stopBtn = el('button',{class:'btn', onclick:()=>{ stop(); set(state, path, t); }}, 'Stop');
  const resetBtn = el('button',{class:'btn btn-red', onclick:reset}, 'Reset');
  update();
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, disp, startBtn, stopBtn, resetBtn)
  );
}

function renderImage(name, path, state){
  const id = `img_${name}_${Math.random().toString(36).slice(2,7)}`;
  const input = el('input',{type:'file', id, accept:'image/*'});
  const note = el('span',{class:'badge'}, 'Not uploaded');
  input.addEventListener('change', async ()=>{
    if (!input.files || !input.files[0]) return;
    const fd = new FormData();
    fd.append('image', input.files[0]);
    const r = await fetch('/api/upload', { method:'POST', body: fd });
    const j = await r.json();
    if (j.path){ set(state, path, j.path); note.textContent = 'Uploaded'; }
  });
  return el('div',{class:'form-row'}, 
    el('label',{for:id}, name), 
    el('div',{class:'form-controls'}, input, note)
  );
}

// Specialized "Scoring object": {Made:int, Missed:int, Value:number in config}
function renderScoring(name, path, state){
  const madePath = path.concat(['Made']);
  const missPath = path.concat(['Missed']);
  set(state, path, {Made:0, Missed:0});
  const made = renderNumber(name+' Made', madePath, state, false);
  const miss = renderNumber(name+' Missed', missPath, state, false);
  return el('div',{}, made, miss);
}

// Make sections collapsible on mobile
function makeSectionCollapsible(sectionElement, defaultCollapsed = false) {
  const header = sectionElement.querySelector('h2');
  if (!header) return;
  
  // Find all content elements (everything except the header)
  const content = Array.from(sectionElement.children).filter(
    child => child !== header.parentElement && !child.classList.contains('section-score')
  );
  
  // Create collapse icon
  const icon = el('span', {class: 'collapse-icon'}, defaultCollapsed ? '▶' : '▼');
  header.parentElement.style.cursor = 'pointer';
  header.insertBefore(icon, header.firstChild);
  
  // Set initial state
  if (defaultCollapsed) {
    content.forEach(item => {
      item.style.display = 'none';
    });
  }
  
  // Add click event to toggle visibility
  header.parentElement.addEventListener('click', (e) => {
    // Don't toggle if clicking on the score display
    if (e.target.classList.contains('section-score')) return;
    
    const isCollapsed = content[0] && content[0].style.display === 'none';
    
    content.forEach(item => {
      item.style.display = isCollapsed ? '' : 'none';
    });
    
    icon.textContent = isCollapsed ? '▼' : '▶';
  });
}

function renderField(name, spec, path, state){
  // Handle different field structures in your config
  const t = (spec.Type || spec.type || '').toLowerCase();
  
  // Handle Boolean with Value FIRST (before the generic Value check)
  if (t === 'boolean with value') return renderBooleanWithValue(name, path, state, spec);
  if (t === 'boolean') return renderBoolean(name, path, state, spec);
  if (t === 'string') return renderString(name, path, state, spec);
  if (t === 'integer' || t === 'typed integer') return renderNumber(name, path, state, false);
  if (t === 'float') return renderNumber(name, path, state, true);
  
  // Handle choice lists with different property names
  if (t.includes('single choice')) {
    const options = spec.options || spec.List || spec.list || [];
    if (spec.values || spec.Values) {
      return renderSingleChoiceWithValue(name, path, state, options, spec.values || spec.Values);
    }
    return renderSingleChoice(name, path, state, options);
  }
  
  if (t.includes('multiple choice')) {
    const options = spec.options || spec.List || spec.list || [];
    if (spec.values || spec.Values) {
      return renderMultipleChoiceWithValue(name, path, state, options, spec.values || spec.Values);
    }
    return renderMultipleChoice(name, path, state, options);
  }
  
  if (t === 'timer') return renderTimer(name, path, state);
  if (t === 'image file' || t === 'picture') return renderImage(name, path, state);
  
  // Composite scoring group with Made/Missed/Value in config (like L1, L2, etc.)
  // This check now comes AFTER the Boolean with Value check
  if (typeof spec === 'object' && ('Made' in spec || ('Value' in spec && t !== 'boolean with value'))) {
    return renderScoring(name, path, state);
  }
  
  // Nested object - recursively render its properties
  if (typeof spec === 'object' && !Array.isArray(spec)) {
    const wrap = el('div', {class: 'nested-field-group'});
    wrap.appendChild(el('h3', {}, name));
    
    // Get keys in order and filter out special properties
    const fieldKeys = Object.keys(spec).filter(k => 
      !['Value', 'Values', 'Made', 'Missed', 'List', 'list', 'options', 'Type', 'type'].includes(k)
    );
    
    fieldKeys.forEach(k => {
      wrap.appendChild(renderField(k, spec[k], path.concat([k]), state));
    });
    return wrap;
  }
  
  // fallback - treat as string
  return renderString(name, path, state);
}

function sectionScore(stateSection, configSection){
  let sum = 0;
  if (!stateSection || !configSection) return 0;
  
  for (const k of Object.keys(stateSection)){
    const v = stateSection[k];
    const c = configSection[k];
    
    // Handle Boolean with Value fields (like left_starting_zone)
    if (typeof v === 'boolean' && c && typeof c.Value === 'number'){
      sum += v ? Number(c.Value||0) : 0;
    }
    // Handle scoring objects with Made/Missed properties
    else if (v && typeof v==='object' && 'Made' in v && c && typeof c.Value==='number'){
      sum += Number(v.Made||0) * Number(c.Value||0);
    }
    // Handle multiple choice with values
    else if (Array.isArray(v) && c && Array.isArray(c.Values)) {
      v.forEach(selectedValue => {
        const index = (c.options || []).indexOf(selectedValue);
        if (index !== -1 && c.Values[index] !== undefined) {
          sum += Number(c.Values[index]) || 0;
        }
      });
    }
  }
  return sum;
}

const OFFLINE_QUEUE_KEY = 'scouting_offline_queue';
const SYNC_INTERVAL = 30000; // 30 seconds

function getOfflineQueue() {
  const queue = localStorage.getItem(OFFLINE_QUEUE_KEY);
  return queue ? JSON.parse(queue) : [];
}

function addToOfflineQueue(type, data) {
  const queue = getOfflineQueue();
  queue.push({
    id: Date.now() + '-' + Math.random().toString(36).substr(2, 9),
    type,
    data,
    timestamp: new Date().toISOString()
  });
  localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(queue));
}

async function processOfflineQueue() {
  if (!navigator.onLine) return;
  
  const queue = getOfflineQueue();
  if (queue.length === 0) return;
  
  console.log(`Processing ${queue.length} offline items...`);
  
  const successful = [];
  
  for (const item of queue) {
    try {
      let response;
      if (item.type === 'match') {
        response = await fetch('/api/matches', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(item.data)
        });
      } else if (item.type === 'pit') {
        response = await fetch('/api/pits', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(item.data)
        });
      }
      
      if (response && response.ok) {
        successful.push(item.id);
      }
    } catch (error) {
      console.error('Error processing offline item:', error);
    }
  }
  
  // Remove successful items from queue
  if (successful.length > 0) {
    const newQueue = queue.filter(item => !successful.includes(item.id));
    localStorage.setItem(OFFLINE_QUEUE_KEY, JSON.stringify(newQueue));
    console.log(`Successfully synced ${successful.length} items`);
    
    // Show notification
    showNotification(`Synced ${successful.length} offline items`);
  }
}

function showNotification(message, isError = false) {
  // Create notification element
  const notification = document.createElement('div');
  notification.className = `notification ${isError ? 'error' : 'success'}`;
  notification.innerHTML = `
    <span>${message}</span>
    <button onclick="this.parentElement.remove()">×</button>
  `;
  
  // Add styles if not already added
  if (!document.querySelector('style#notification-styles')) {
    const styles = document.createElement('style');
    styles.id = 'notification-styles';
    styles.textContent = `
      .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px;
        border-radius: 5px;
        color: white;
        z-index: 1000;
        display: flex;
        align-items: center;
        justify-content: space-between;
        min-width: 300px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      }
      .notification.success { background: #28a745; }
      .notification.error { background: #dc3545; }
      .notification button {
        background: none;
        border: none;
        color: white;
        font-size: 20px;
        cursor: pointer;
        margin-left: 15px;
      }
    `;
    document.head.appendChild(styles);
  }
  
  document.body.appendChild(notification);
  
  // Auto-remove after 5 seconds
  setTimeout(() => {
    if (notification.parentElement) {
      notification.remove();
    }
  }, 5000);
}

// Check online status and setup sync
function setupOfflineSync() {
  // Process queue on load if online
  if (navigator.onLine) {
    setTimeout(processOfflineQueue, 2000);
  }
  
  // Process queue when coming online
  window.addEventListener('online', processOfflineQueue);
  
  // Regularly process queue
  setInterval(processOfflineQueue, SYNC_INTERVAL);
  
  // Show offline indicator
  function updateOnlineStatus() {
    if (!navigator.onLine) {
      showNotification('You are offline. Data will be saved locally and synced when connection is restored.', true);
    }
  }
  
  window.addEventListener('offline', updateOnlineStatus);
  window.addEventListener('online', () => {
    showNotification('Connection restored. Syncing offline data...');
  });
}

// Initialize offline sync
setupOfflineSync();

export async function buildMatchForm(root, totalsEl){
  const conf = await loadConfig();
  const state = { pre_match_json:{}, auto_json:{}, teleop_json:{}, endgame_json:{}, misc_json:{} };
  const isMobile = window.innerWidth <= 768;

  // Create score displays for each section
  const autoScoreEl = el('div', {class: 'section-score'}, 'Auto: 0');
  const teleopScoreEl = el('div', {class: 'section-score'}, 'Teleop: 0');
  const endgameScoreEl = el('div', {class: 'section-score'}, 'Endgame: 0');

  // Function to add sections in config order
  const addSection = (title, spec, key, scoreEl = null) => {
    const card = el('div', {class: 'card'});
    const header = el('div', {class: 'section-header'});
    header.appendChild(el('h2', {}, title));
    if (scoreEl) header.appendChild(scoreEl);
    card.appendChild(header);
    
    // Get field keys in exact order from config
    const fieldKeys = Object.keys(spec || {});
    
    // Render fields in the order they appear in the config
    fieldKeys.forEach(field => {
      // Skip special properties that shouldn't be rendered as fields
      if (['Value', 'Values'].includes(field)) return;
      
      // Special handling for final_status field with values
      if (field === 'final_status' && spec[field].options && spec[field].values) {
        card.appendChild(renderSingleChoiceWithValue(
          field, 
          [key, field], 
          state, 
          spec[field].options, 
          spec[field].values
        ));
      } 
      // Handle Boolean with Value fields (like left_starting_zone) - check type first!
      else if (spec[field] && typeof spec[field] === 'object' && 
              (spec[field].type === 'Boolean with Value' || spec[field].Type === 'Boolean with Value')) {
        card.appendChild(renderBooleanWithValue(field, [key, field], state, spec[field]));
      }
      // Handle scoring objects (L1, L2, etc. in auto_period and teleop_period)
      else if (spec[field] && typeof spec[field] === 'object' && 
              ('Made' in spec[field] || ('Value' in spec[field] && 
              spec[field].type !== 'Boolean with Value' && spec[field].Type !== 'Boolean with Value'))) {
        card.appendChild(renderScoring(field, [key, field], state));
      }
      // Handle all other field types
      else {
        card.appendChild(renderField(field, spec[field], [key, field], state));
      }
    });
    
    // Make all sections collapsible on mobile, starting collapsed
    if (isMobile) {
      makeSectionCollapsible(card, true);
    }
    
    root.appendChild(card);
  };

  // Render sections in the exact order they appear in config.json
  const matchFormConfig = conf.match_form;
  
  // Pre-Match Info (first section)
  addSection('Pre-Match Info', matchFormConfig['pre-match_info'], 'pre_match_json');
  
  // Autonomous Period
  addSection('Autonomous Period', matchFormConfig.auto_period, 'auto_json', autoScoreEl);
  
  // Teleop Period
  addSection('Teleop Period', matchFormConfig.teleop_period, 'teleop_json', teleopScoreEl);
  
  // Endgame
  const endgameSpec = matchFormConfig.endgame;
  const endgameCard = el('div',{class:'card'});
  const endgameHeader = el('div', {class: 'section-header'});
  endgameHeader.appendChild(el('h2',{}, 'Endgame'));
  endgameHeader.appendChild(endgameScoreEl);
  endgameCard.appendChild(endgameHeader);
  
  // Get field keys in order for endgame section
  const endgameFieldKeys = Object.keys(endgameSpec||{}).filter(field => 
    !['Value', 'Values'].includes(field)
  );
  
  endgameFieldKeys.forEach(field=>{
    if (field === 'final_status' && endgameSpec[field].options && endgameSpec[field].values) {
      endgameCard.appendChild(renderSingleChoiceWithValue(
        field, 
        ['endgame_json', field], 
        state, 
        endgameSpec[field].options, 
        endgameSpec[field].values
      ));
    } else {
      endgameCard.appendChild(renderField(field, endgameSpec[field], ['endgame_json', field], state));
    }
  });
  
  // Make endgame section collapsible on mobile, starting collapsed
  if (isMobile) {
    makeSectionCollapsible(endgameCard, true); // true means start collapsed
  }
  
  root.appendChild(endgameCard);
  
  // Miscellaneous (last section)
  addSection('Miscellaneous', matchFormConfig.misc, 'misc_json');

  function updateTotals(){
    const a = sectionScore(state.auto_json, conf.match_form.auto_period);
    const t = sectionScore(state.teleop_json, conf.match_form.teleop_period);
    
    // Calculate endgame score from final_status with values
    let e = 0;
    const fs = state.endgame_json.final_status;
    const finMap = conf.match_form.endgame.final_status;
    
    if (fs && finMap && finMap.options && finMap.values) {
      const index = finMap.options.indexOf(fs);
      if (index !== -1 && finMap.values[index] !== undefined) {
        e = Number(finMap.values[index]) || 0;
      }
    }
    
    // Update section scores
    autoScoreEl.textContent = `Auto: ${a}`;
    teleopScoreEl.textContent = `Teleop: ${t}`;
    endgameScoreEl.textContent = `Endgame: ` + e;
    
    totalsEl.innerHTML = `<b>Auto:</b> ${a} &nbsp; <b>Teleop:</b> ${t} &nbsp; <b>Endgame:</b> ${e} &nbsp; <b>Total:</b> ${a+t+e}`;
  }
  setInterval(updateTotals, 250);

  return {
    getState: ()=>state,
    submit: async ()=>{
      try {
        const r = await fetch('/api/matches',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(state)});
        if (r.ok) {
          return r.json();
        } else {
          throw new Error('Server error');
        }
      } catch (error) {
        // Save to offline queue
        addToOfflineQueue('match', state);
        showNotification('Offline - Data saved locally and will sync when connection is restored');
        return { id: 'offline-' + Date.now(), offline: true };
      }
    }
  };
}

export async function buildPitForm(root){
  const conf = await loadConfig();
  const state = { pit_json:{} , image_path:null };
  const isMobile = window.innerWidth <= 768;

  const spec = conf.pit_form.fields || {};
  const card = el('div',{class:'card'}); 
  card.appendChild(el('h2',{}, 'Pit Scouting'));
  
  // Get field keys in order for pit form
  const fieldKeys = Object.keys(spec);
  
  // Render fields in the order they appear in the config
  fieldKeys.forEach(field=>{
    if (field.toLowerCase().includes('picture') || (spec[field].Type||'').toLowerCase()==='image file'){
      card.appendChild(renderImage(field, ['image_path'], state));
    }else{
      card.appendChild(renderField(field, spec[field], ['pit_json', field], state));
    }
  });
  
  // Make pit form collapsible on mobile, starting collapsed
  if (isMobile) {
    makeSectionCollapsible(card, true); // true means start collapsed
  }
  
  root.appendChild(card);

  return {
    getState: ()=>state,
    submit: async ()=>{
      try {
        const r = await fetch('/api/pits', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(state)});
        if (r.ok) {
          return r.json();
        } else {
          throw new Error('Server error');
        }
      } catch (error) {
        // Save to offline queue
        addToOfflineQueue('pit', state);
        showNotification('Offline - Data saved locally and will sync when connection is restored');
        return { id: 'offline-' + Date.now(), offline: true };
      }
    }
  };
}