// State
let tasks = [];
let categories = [];
let collapsedCategories = new Set();
let collapsedStatsCategories = new Set();
let currentStatFilter = 'hoy'; // 'hoy', 'semana', 'mes'

// DOM Elements
const taskForm = document.getElementById('add-task-form');
const titleInput = document.getElementById('task-title');
const categorySelect = document.getElementById('task-category');
const prioritySelect = document.getElementById('task-priority');
const tasksContainer = document.getElementById('tasks-container');

const addCatForm = document.getElementById('add-category-form');
const catNameInput = document.getElementById('cat-name');
const catColorInput = document.getElementById('cat-color');
const categoriesList = document.getElementById('categories-list');

const iconSelectorBtn = document.getElementById('icon-selector-btn');
const iconPopover = document.getElementById('icon-popover');
const iconGrid = document.getElementById('icon-grid');
const selectedIconDisplay = document.getElementById('selected-icon-display');

let selectedCatIcon = 'label';
const availableIcons = [
    'label', 'star', 'bookmark', 'work', 'laptop_mac', 'business_center', 
    'school', 'menu_book', 'edit_document', 'home', 'person', 'favorite', 
    'shopping_cart', 'fitness_center', 'restaurant', 'flight', 'palette', 
    'sports_esports', 'music_note', 'savings', 'attach_money',
    'analytics', 'auto_graph', 'bar_chart', 'account_balance', 'trending_up', 'how_to_vote'
];

// Stats Elements
const statHoy = document.getElementById('stat-hoy');
const statSemana = document.getElementById('stat-semana');
const statMes = document.getElementById('stat-mes');
const completedTasksContainer = document.getElementById('completed-tasks-container');
const filterBtns = document.querySelectorAll('.filter-btn');

// ─── API Functions (PyWebView) ───────────────────────────────────────────────
// En lugar de fetch() al servidor HTTP, usamos window.pywebview.api
// que llama directamente a métodos Python de la clase TaskAPI en main.py.

async function loadData() {
    try {
        const data = await window.pywebview.api.get_data();
        tasks = data.tasks || [];
        categories = data.categories || [];
        
        renderCategories();
        updateCategorySelects();
        renderTasks();
        renderStats();
    } catch (error) {
        console.error(error);
        tasksContainer.innerHTML = '<div class="text-center p-8 text-on-surface-variant font-medium">Error cargando las tareas.</div>';
    }
}

async function saveData() {
    try {
        await window.pywebview.api.save_data({ tasks, categories });
    } catch (error) {
        console.error('Error saving data:', error);
        alert('Hubo un error al guardar los datos.');
    }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function getCategory(id) {
    return categories.find(c => c.id === id) || { name: 'Sin categoría', color: '#8b7d6b' };
}

function hexToRgba(hex, alpha) {
    const r = parseInt(hex.slice(1, 3), 16) || 0;
    const g = parseInt(hex.slice(3, 5), 16) || 0;
    const b = parseInt(hex.slice(5, 7), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function isDateInRange(dateString, range) {
    if (!dateString) return false;
    const date = new Date(dateString);
    const now = new Date();
    
    // Reset times to start of day for accurate comparison
    const dateDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    const nowDay = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    
    const diffTime = Math.abs(nowDay - dateDay);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24)); 
    
    if (range === 'hoy') return diffDays === 0;
    if (range === 'semana') return diffDays <= 7;
    if (range === 'mes') return diffDays <= 30;
    return false;
}

// ─── Render Functions ────────────────────────────────────────────────────────

function renderCategories() {
    categoriesList.innerHTML = '';
    
    categories.forEach(cat => {
        const span = document.createElement('span');
        span.className = 'px-3 py-1.5 rounded-full text-xs font-semibold tracking-wide flex items-center gap-1 group';
        span.style.backgroundColor = hexToRgba(cat.color, 0.15);
        span.style.color = cat.color;
        
        span.innerHTML = `
            ${cat.name}
            <button class="delete-cat-btn ml-1 opacity-50 hover:opacity-100 hover:text-error transition-all" data-id="${cat.id}">
                <i class="fa-solid fa-xmark"></i>
            </button>
        `;
        categoriesList.appendChild(span);
    });

    // Add delete listeners
    document.querySelectorAll('.delete-cat-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            deleteCategory(e.currentTarget.dataset.id);
        });
    });
}

function updateCategorySelects() {
    const currentVal = categorySelect.value;
    
    let optionsHTML = '<option value="" disabled selected>Categoría</option>';
    categories.forEach(cat => {
        optionsHTML += `<option value="${cat.id}">${cat.name}</option>`;
    });

    categorySelect.innerHTML = optionsHTML;

    if (currentVal && categories.find(c => c.id === currentVal)) {
        categorySelect.value = currentVal;
    }
}

function renderTasks() {
    // Solo tareas no completadas
    const pendingTasks = tasks.filter(t => !t.completed);

    if (pendingTasks.length === 0) {
        tasksContainer.innerHTML = `
            <div class="bg-surface-container-low rounded-xl p-8 text-center text-on-surface-variant flex flex-col items-center gap-2">
                <span class="material-symbols-outlined text-[48px] opacity-20">done_all</span>
                <span class="font-medium">No hay tareas pendientes. ¡Tómate un descanso!</span>
            </div>
        `;
        return;
    }

    tasksContainer.innerHTML = '';

    // Group tasks by category
    const groupedTasks = {};
    pendingTasks.forEach(task => {
        const catId = task.categoryId;
        if (!groupedTasks[catId]) groupedTasks[catId] = [];
        groupedTasks[catId].push(task);
    });

    // Render each group
    for (const [catId, groupTasks] of Object.entries(groupedTasks)) {
        const cat = getCategory(catId);
        const isCollapsed = collapsedCategories.has(catId);
        
        const groupDiv = document.createElement('div');
        groupDiv.className = 'rounded-xl p-6 relative overflow-hidden transition-all duration-300';
        groupDiv.style.backgroundColor = hexToRgba(cat.color, 0.05);

        // Ribbon
        const ribbon = document.createElement('div');
        ribbon.className = 'absolute left-0 top-0 bottom-0 w-1.5';
        ribbon.style.backgroundColor = hexToRgba(cat.color, 0.3);
        groupDiv.appendChild(ribbon);

        // Header
        const header = document.createElement('h3');
        header.className = 'font-headline text-lg font-semibold mb-4 ml-2 flex items-center gap-2 cursor-pointer select-none';
        header.style.color = cat.color;
        
        const iconName = cat.icon || 'label';

        header.innerHTML = `
            <div class="flex items-center justify-between w-full">
                <div class="flex items-center gap-2">
                    <span class="material-symbols-outlined text-[20px]">${iconName}</span>
                    ${cat.name} <span class="text-sm opacity-50 font-normal">(${groupTasks.length})</span>
                </div>
                <span class="material-symbols-outlined transition-transform duration-300 ${isCollapsed ? '-rotate-90' : ''}" style="color: ${hexToRgba(cat.color, 0.6)}">expand_more</span>
            </div>
        `;
        
        header.addEventListener('click', () => {
            if (collapsedCategories.has(catId)) collapsedCategories.delete(catId);
            else collapsedCategories.add(catId);
            renderTasks();
        });
        
        groupDiv.appendChild(header);

        // Tasks container
        const contentDiv = document.createElement('div');
        contentDiv.className = `flex flex-col gap-3 transition-all duration-300 ${isCollapsed ? 'hidden' : 'block'}`;
        
        groupTasks.forEach(task => {
            const div = document.createElement('div');
            div.className = 'bg-surface-container-lowest p-4 rounded-xl flex items-start gap-4 group hover:shadow-[0_8px_24px_rgba(27,28,26,0.04)] transition-all border-l-2 border-transparent';
            
            // Priority Tag HTML
            let priorityHtml = '';
            if (task.priority === 'Alta') {
                priorityHtml = `<span class="px-2 py-0.5 bg-error-container text-error text-[10px] font-bold rounded-md uppercase tracking-wide w-fit whitespace-nowrap">Alta</span>`;
            } else if (task.priority === 'Media') {
                priorityHtml = `<span class="px-2 py-0.5 bg-primary-container/30 text-primary text-[10px] font-bold rounded-md uppercase tracking-wide w-fit whitespace-nowrap">Media</span>`;
            } else if (task.priority === 'Baja') {
                priorityHtml = `<span class="px-2 py-0.5 bg-secondary-container/30 text-secondary text-[10px] font-bold rounded-md uppercase tracking-wide w-fit whitespace-nowrap">Baja</span>`;
            }

            div.innerHTML = `
                <button class="checkbox-custom w-5 h-5 mt-0.5 rounded-md border-2 border-outline-variant flex items-center justify-center hover:border-primary transition-colors flex-shrink-0" data-id="${task.id}"></button>
                <div class="flex items-center gap-3 flex-1 overflow-hidden">
                    <span class="font-medium text-on-surface text-base truncate">${task.title}</span>
                    ${priorityHtml}
                </div>
                <button class="delete-task-btn w-8 h-8 rounded-full flex items-center justify-center text-outline hover:bg-error-container hover:text-error transition-colors opacity-0 group-hover:opacity-100" data-id="${task.id}" title="Eliminar">
                    <span class="material-symbols-outlined text-[18px]">delete</span>
                </button>
            `;
            
            // Hover effect for left border
            div.addEventListener('mouseenter', () => div.style.borderLeftColor = hexToRgba(cat.color, 0.3));
            div.addEventListener('mouseleave', () => div.style.borderLeftColor = 'transparent');
            
            contentDiv.appendChild(div);
        });

        groupDiv.appendChild(contentDiv);
        tasksContainer.appendChild(groupDiv);
    }

    // Add listeners
    document.querySelectorAll('.checkbox-custom').forEach(cb => {
        cb.addEventListener('click', (e) => {
            toggleTaskComplete(e.currentTarget.dataset.id, true);
        });
    });

    document.querySelectorAll('.delete-task-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            deleteTask(e.currentTarget.dataset.id);
        });
    });
}

function renderStats() {
    const completedTasks = tasks.filter(t => t.completed);
    
    // Calculate global stats
    const countHoy = completedTasks.filter(t => isDateInRange(t.completedAt, 'hoy')).length;
    const countSemana = completedTasks.filter(t => isDateInRange(t.completedAt, 'semana')).length;
    const countMes = completedTasks.filter(t => isDateInRange(t.completedAt, 'mes')).length;
    
    statHoy.textContent = countHoy;
    statSemana.textContent = countSemana;
    statMes.textContent = countMes;

    // Filter tasks for the list
    const filteredStatsTasks = completedTasks.filter(t => isDateInRange(t.completedAt, currentStatFilter));
    
    // Group by category
    const groupedStats = {};
    filteredStatsTasks.forEach(task => {
        const catId = task.categoryId;
        if (!groupedStats[catId]) groupedStats[catId] = [];
        groupedStats[catId].push(task);
    });

    completedTasksContainer.innerHTML = '';

    if (Object.keys(groupedStats).length === 0) {
        completedTasksContainer.innerHTML = '<div class="text-center text-sm text-on-surface-variant p-2">No hay tareas completadas en este periodo.</div>';
        return;
    }

    for (const [catId, groupTasks] of Object.entries(groupedStats)) {
        const cat = getCategory(catId);
        const isCollapsed = collapsedStatsCategories.has(catId);
        
        const catDiv = document.createElement('div');
        catDiv.className = 'flex flex-col gap-2';

        const header = document.createElement('div');
        header.className = 'flex items-center justify-between cursor-pointer hover:bg-surface-container p-1 rounded-md transition-colors';
        header.innerHTML = `
            <div class="flex items-center gap-2">
                <div class="w-2 h-2 rounded-full" style="background-color: ${cat.color}"></div>
                <span class="text-sm text-on-surface-variant font-medium">${cat.name}</span>
            </div>
            <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-on-surface">${groupTasks.length}</span>
                <span class="material-symbols-outlined text-[16px] text-on-surface-variant transition-transform ${isCollapsed ? 'rotate-180' : ''}">keyboard_arrow_down</span>
            </div>
        `;
        
        header.addEventListener('click', () => {
            if (collapsedStatsCategories.has(catId)) collapsedStatsCategories.delete(catId);
            else collapsedStatsCategories.add(catId);
            renderStats();
        });

        catDiv.appendChild(header);

        if (!isCollapsed) {
            const listDiv = document.createElement('div');
            listDiv.className = 'flex flex-col gap-1 pl-4 border-l border-outline-variant/30 ml-1 mb-2';
            
            groupTasks.forEach(task => {
                const taskDiv = document.createElement('div');
                taskDiv.className = 'flex items-center justify-between group/stat';
                taskDiv.innerHTML = `
                    <span class="text-[13px] text-on-surface-variant/80 line-through truncate max-w-[200px]">${task.title}</span>
                    <button class="restore-task-btn text-[12px] text-primary opacity-0 group-hover/stat:opacity-100 transition-opacity cursor-pointer hover:underline" data-id="${task.id}">Restaurar</button>
                `;
                listDiv.appendChild(taskDiv);
            });
            catDiv.appendChild(listDiv);
        }

        completedTasksContainer.appendChild(catDiv);
    }
    
    // Restore listeners
    document.querySelectorAll('.restore-task-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            toggleTaskComplete(e.currentTarget.dataset.id, false);
        });
    });
}

// ─── Actions ─────────────────────────────────────────────────────────────────

async function addTask(e) {
    e.preventDefault();
    const title = titleInput.value.trim();
    const categoryId = categorySelect.value;
    const priority = prioritySelect.value;

    if (!title || !categoryId) return;

    const newTask = {
        id: 'task-' + Date.now(),
        title,
        categoryId,
        priority,
        completed: false
    };

    tasks.push(newTask);
    titleInput.value = '';
    
    collapsedCategories.delete(categoryId);
    
    renderTasks();
    await saveData();
}

async function toggleTaskComplete(id, isCompleted) {
    const task = tasks.find(t => t.id === id);
    if (task) {
        task.completed = isCompleted;
        if (isCompleted) {
            task.completedAt = new Date().toISOString();
        } else {
            delete task.completedAt;
        }
        renderTasks();
        renderStats();
        await saveData();
    }
}

async function deleteTask(id) {
    tasks = tasks.filter(t => t.id !== id);
    renderTasks();
    renderStats();
    await saveData();
}

async function addCategory(e) {
    e.preventDefault();
    const name = catNameInput.value.trim();
    const color = catColorInput.value;

    if (!name) return;

    const newCat = {
        id: 'cat-' + Date.now(),
        name,
        color,
        icon: selectedCatIcon
    };

    categories.push(newCat);
    catNameInput.value = '';
    selectedCatIcon = 'label';
    selectedIconDisplay.textContent = 'label';
    
    renderCategories();
    updateCategorySelects();
    await saveData();
}

async function deleteCategory(id) {
    const inUse = tasks.some(t => t.categoryId === id);
    if (inUse) {
        alert('No puedes eliminar una categoría que está siendo usada por tareas.');
        return;
    }

    categories = categories.filter(c => c.id !== id);
    renderCategories();
    updateCategorySelects();
    await saveData();
}

// ─── Event Listeners ─────────────────────────────────────────────────────────

taskForm.addEventListener('submit', addTask);
addCatForm.addEventListener('submit', addCategory);

// Icon Selector Initialization
function initIconSelector() {
    availableIcons.forEach(icon => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'w-10 h-10 rounded-lg flex items-center justify-center hover:bg-surface-container-high transition-colors text-on-surface-variant hover:text-primary';
        btn.innerHTML = `<span class="material-symbols-outlined text-[20px]">${icon}</span>`;
        btn.addEventListener('click', () => {
            selectedCatIcon = icon;
            selectedIconDisplay.textContent = icon;
            iconPopover.classList.add('hidden');
        });
        iconGrid.appendChild(btn);
    });

    iconSelectorBtn.addEventListener('click', (e) => {
        e.preventDefault();
        iconPopover.classList.toggle('hidden');
    });

    document.addEventListener('click', (e) => {
        if (!iconSelectorBtn.contains(e.target) && !iconPopover.contains(e.target)) {
            iconPopover.classList.add('hidden');
        }
    });
}
initIconSelector();

// Filter buttons listener
filterBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
        const filter = e.currentTarget.dataset.filter;
        currentStatFilter = filter;
        
        // Update active classes
        filterBtns.forEach(b => {
            b.classList.remove('bg-surface-container-lowest', 'text-primary', 'font-bold', 'shadow-sm');
            b.classList.add('text-on-surface-variant', 'font-medium', 'hover:text-on-surface');
        });
        e.currentTarget.classList.add('bg-surface-container-lowest', 'text-primary', 'font-bold', 'shadow-sm');
        e.currentTarget.classList.remove('text-on-surface-variant', 'font-medium', 'hover:text-on-surface');
        
        renderStats();
    });
});

// ─── Init ────────────────────────────────────────────────────────────────────
// Esperar a que pywebview exponga la API antes de cargar datos
window.addEventListener('pywebviewready', () => {
    loadData();
});
