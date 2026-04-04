<template>
  <div class="cabinet-page">
    <transition name="menu-overlay">
      <div
        v-if="menuOpen"
        class="side-menu-overlay"
        @click="closeMenu"
      ></div>
    </transition>

    <transition name="side-menu">
      <aside v-if="menuOpen" class="side-menu">
        <div class="side-menu-top">
          <button class="side-menu-close" @click="closeMenu">×</button>
        </div>

        <div class="side-menu-section">
          <button class="side-menu-item active" @click="goToProfile">
            Профиль
          </button>
          <button class="side-menu-item" @click="goToSchedule">
            Расписание
          </button>
        </div>

        <div class="side-menu-footer">
          <button class="side-menu-item side-menu-item-danger" @click="handleLogout">
            Выйти
          </button>
        </div>
      </aside>
    </transition>

    <header class="cabinet-header">
      <div class="cabinet-header-actions">
        <button class="menu-button" @click="openMenu" aria-label="Открыть меню">
          <span></span>
          <span></span>
          <span></span>
        </button>
        <img :src="logoSupra" alt="Supra" class="cabinet-brand-logo" />
        <NotificationBell />
      </div>
    </header>

    <main class="cabinet-content">
      <section class="profile-card">
        <div class="profile-card-top">
          <div class="profile-heading">
            <p class="profile-subtitle">Личный кабинет</p>
            <h1 class="cabinet-title">Профиль</h1>
          </div>
        </div>

        <div class="profile-info-block">
          <p><strong>Логин:</strong> {{ user.username }}</p>
          <p><strong>Email:</strong> {{ user.email }}</p>
          <p><strong>Имя:</strong> {{ user.first_name }}</p>
          <p><strong>Фамилия:</strong> {{ user.last_name }}</p>
          <p><strong>Телефон:</strong> {{ user.phone || 'Не указан' }}</p>
          <p><strong>Роль:</strong> {{ roleRu }}</p>
          <p><strong>Заведение:</strong> {{ currentVenueLabel }}</p>
        </div>

        <div class="manager-actions">
          <button v-if="currentUserRole === 'admin'" class="wide-button" @click="openUploadDataModal">
            Загрузить данные
          </button>

          <button
            v-if="currentUserRole === 'admin'"
            class="wide-button"
            :disabled="isRunningForecastPipeline"
            @click="runAdminModelTraining"
          >
            {{ isRunningForecastPipeline ? 'Обучаем...' : 'Обучить модель' }}
          </button>

          <div v-if="currentUserRole === 'admin' && forecastRunError" class="form-alert error">
            {{ forecastRunError }}
          </div>

          <div v-if="currentUserRole === 'admin' && forecastRunSuccess" class="form-alert success">
            {{ forecastRunSuccess }}
          </div>

          <button v-if="currentUserRole === 'admin'" class="wide-button secondary" @click="openCreateVenueModal">
            Создать заведение
          </button>

          <button class="wide-button secondary" @click="openEmployeesModal">
            Просмотр сотрудников
          </button>

          <button
            v-if="canManagePeople"
            class="wide-button secondary"
            @click="openCreateRoleModal"
          >
            Создание сотрудника
          </button>
        </div>
      </section>
    </main>

    <transition name="modal-fade">
      <div v-if="showEmployeesModal" class="modal-overlay" @click.self="closeEmployeesModal">
        <div class="modal-card employees-modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">Команда</p>
              <h2 class="modal-title">Сотрудники</h2>
            </div>
            <button class="modal-close" @click="closeEmployeesModal">×</button>
          </div>

          <div class="role-groups">
            <div class="role-stat-card">
              <span class="role-stat-label">Админы</span>
              <strong class="role-stat-value">{{ groupedEmployees.admin.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Менеджеры</span>
              <strong class="role-stat-value">{{ groupedEmployees.manager.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Официанты-стажеры</span>
              <strong class="role-stat-value">{{ groupedEmployees.employee_noob.length }}</strong>
            </div>
            <div class="role-stat-card">
              <span class="role-stat-label">Официанты-профи</span>
              <strong class="role-stat-value">{{ groupedEmployees.employee_pro.length }}</strong>
            </div>
          </div>

          <div v-if="isLoadingEmployees" class="form-alert success">
            Загружаем список сотрудников...
          </div>

          <div v-else-if="employeesError" class="form-alert error">
            {{ employeesError }}
          </div>

          <div v-else class="employee-sections">
            <section
              v-for="section in employeeSections"
              :key="section.key"
              class="employee-section"
            >
              <div class="employee-section-head">
                <h3>{{ section.title }}</h3>
                <span>{{ section.items.length }}</span>
              </div>

              <div v-if="section.items.length === 0" class="employee-empty">
                Нет сотрудников в этой группе
              </div>

              <div v-else class="employee-list">
                <article
                  v-for="employee in section.items"
                  :key="employee.id || employee.username"
                  class="employee-card"
                >
                  <div class="employee-card-head">
                    <strong>{{ getEmployeeFullName(employee) }}</strong>
                    <span class="employee-role-chip">{{ getRoleLabel(employee.role) }}</span>
                  </div>
                  <p>{{ employee.username }}</p>
                  <p>{{ employee.email || 'Email не указан' }}</p>
                  <p>{{ employee.phone || 'Телефон не указан' }}</p>
                  <p>Заведение: {{ getVenueLabel(employee) }}</p>
                  <div v-if="canAdminManageEmployee(employee)" class="employee-card-actions">
                    <button class="employee-manage-button" type="button" @click="openManageEmployeeModal(employee)">
                      Управление
                    </button>
                  </div>
                </article>
              </div>
            </section>
          </div>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="showManageEmployeeModal" class="modal-overlay" @click.self="closeManageEmployeeModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">Admin</p>
              <h2 class="modal-title">Управление сотрудником</h2>
            </div>
            <button class="modal-close" @click="closeManageEmployeeModal">×</button>
          </div>

          <form class="role-form" @submit.prevent="submitManageEmployee">
            <div v-if="manageEmployeeError" class="form-alert error">
              {{ manageEmployeeError }}
            </div>

            <div v-if="manageEmployeeSuccess" class="form-alert success">
              {{ manageEmployeeSuccess }}
            </div>

            <div v-if="isLoadingManagedEmployee" class="form-alert success">
              Загружаем данные сотрудника...
            </div>

            <div v-else class="form-grid">
              <label class="form-field">
                <span>Username *</span>
                <input v-model.trim="manageEmployeeForm.username" type="text" required :disabled="isSavingManagedEmployee" />
              </label>

              <label class="form-field">
                <span>Email *</span>
                <input v-model.trim="manageEmployeeForm.email" type="email" required :disabled="isSavingManagedEmployee" />
              </label>

              <label class="form-field">
                <span>Имя *</span>
                <input v-model.trim="manageEmployeeForm.first_name" type="text" required :disabled="isSavingManagedEmployee" />
              </label>

              <label class="form-field">
                <span>Фамилия *</span>
                <input v-model.trim="manageEmployeeForm.last_name" type="text" required :disabled="isSavingManagedEmployee" />
              </label>

              <label class="form-field">
                <span>Телефон</span>
                <input v-model.trim="manageEmployeeForm.phone" type="tel" :disabled="isSavingManagedEmployee" />
              </label>

              <label class="form-field">
                <span>Роль *</span>
                <ThemedSelect
                  v-model="manageEmployeeForm.role"
                  :options="availableRoleOptions"
                  :disabled="isSavingManagedEmployee"
                />
              </label>

              <label class="form-field form-field-full">
                <span>Заведение</span>
                <ThemedSelect
                  v-model="manageEmployeeForm.venue"
                  :options="manageVenueOptions"
                  :disabled="isSavingManagedEmployee"
                  placeholder="Без заведения"
                />
              </label>
            </div>

            <div class="form-actions">
              <button type="button" class="wide-button secondary" :disabled="isSavingManagedEmployee || isLoadingManagedEmployee" @click="closeManageEmployeeModal">
                Отмена
              </button>
              <button type="submit" class="wide-button" :disabled="isSavingManagedEmployee || isLoadingManagedEmployee || !manageEmployeeForm.id">
                {{ isSavingManagedEmployee ? 'Сохраняем...' : 'Сохранить изменения' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="showCreateRoleModal" class="modal-overlay" @click.self="closeCreateRoleModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">{{ roleRu }}</p>
              <h2 class="modal-title">Создание сотрудника</h2>
            </div>
            <button class="modal-close" @click="closeCreateRoleModal">×</button>
          </div>

          <form class="role-form" @submit.prevent="submitCreateRole">
            <div v-if="createRoleError" class="form-alert error">
              {{ createRoleError }}
            </div>

            <div v-if="createRoleSuccess" class="form-alert success">
              {{ createRoleSuccess }}
            </div>

            <div v-if="copyNotice" class="copy-notice">
              {{ copyNotice }}
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>Username *</span>
                <input
                  v-model.trim="createRoleForm.username"
                  type="text"
                  placeholder="nickname"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Email *</span>
                <input
                  v-model.trim="createRoleForm.email"
                  type="email"
                  placeholder="bagbag@gmail.com"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Имя *</span>
                <input
                  v-model.trim="createRoleForm.first_name"
                  type="text"
                  placeholder="имя"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Фамилия *</span>
                <input
                  v-model.trim="createRoleForm.last_name"
                  type="text"
                  placeholder="фамилия"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Пароль *</span>
                <input
                  v-model="createRoleForm.password"
                  type="text"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Подтверждение пароля *</span>
                <input
                  v-model="createRoleForm.password_confirm"
                  type="text"
                  placeholder="********"
                  minlength="8"
                  required
                  :disabled="isCreatingRole"
                />
              </label>

              <div class="form-field form-field-full">
                <button
                  type="button"
                  class="copy-button copy-button-wide"
                  :disabled="!createRoleForm.username || !createRoleForm.password || isCreatingRole"
                  @click="copyCredentials"
                >
                  Скопировать логин и пароль
                </button>
              </div>

              <label class="form-field">
                <span>Телефон</span>
                <input
                  v-model.trim="createRoleForm.phone"
                  type="tel"
                  placeholder="+79990007766"
                  :disabled="isCreatingRole"
                />
              </label>

              <label class="form-field">
                <span>Роль *</span>
                <ThemedSelect
                  v-model="createRoleForm.role"
                  :options="availableRoleOptions"
                  :disabled="isCreatingRole"
                />
              </label>

              <label
                v-if="currentUserRole === 'manager'"
                class="form-field form-field-full"
              >
                <span>Заведение</span>
                <input
                  :value="currentVenueLabel"
                  type="text"
                  disabled
                />
              </label>

              <label
                v-if="currentUserRole === 'admin'"
                class="form-field form-field-full"
              >
                <span>Заведение</span>
                <ThemedSelect
                  v-model="createRoleForm.venue"
                  :options="venueOptions"
                  :disabled="isCreatingRole"
                  placeholder="Выберите ресторан"
                />
              </label>
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="wide-button secondary"
                @click="closeCreateRoleModal"
                :disabled="isCreatingRole"
              >
                Отмена
              </button>
              <button type="submit" class="wide-button" :disabled="isCreatingRole">
                {{ isCreatingRole ? 'Создание...' : 'Создать сотрудника' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="showUploadDataModal" class="modal-overlay" @click.self="closeUploadDataModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">Admin</p>
              <h2 class="modal-title">Загрузка исторических данных</h2>
            </div>
            <button class="modal-close" @click="closeUploadDataModal">×</button>
          </div>

          <form class="role-form" @submit.prevent="submitForecastDataUpload">
            <div v-if="uploadDataError" class="form-alert error">
              {{ uploadDataError }}
            </div>

            <div v-if="uploadDataSuccess" class="form-alert success">
              {{ uploadDataSuccess }}
            </div>

            <div class="form-grid">
              <label class="form-field form-field-full">
                <span>Файл с данными *</span>
                <input
                  type="file"
                  accept=".xlsx,.xls,.csv,.json,application/json,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel"
                  :disabled="isUploadingForecastData"
                  @change="handleForecastFileChange"
                />
              </label>

              <label class="form-field form-field-full">
                <span>Заведение по умолчанию</span>
                <ThemedSelect
                  v-model="forecastUploadVenueId"
                  :options="forecastVenueOptions"
                  :disabled="isUploadingForecastData"
                  placeholder="Из файла или не указывать"
                />
              </label>
            </div>

          

            <div v-if="forecastUploadFileName" class="upload-preview-card">
              <p v-if="forecastUploadFileName"><strong>Файл:</strong> {{ forecastUploadFileName }}</p>
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="wide-button secondary"
                :disabled="isUploadingForecastData"
                @click="closeUploadDataModal"
              >
                Отмена
              </button>
              <button
                type="submit"
                class="wide-button"
                :disabled="isUploadingForecastData"
              >
                {{ isUploadingForecastData ? 'Загружаем...' : 'Отправить в БД' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>

    <transition name="modal-fade">
      <div v-if="showCreateVenueModal" class="modal-overlay" @click.self="closeCreateVenueModal">
        <div class="modal-card">
          <div class="modal-header">
            <div>
              <p class="modal-subtitle">Admin</p>
              <h2 class="modal-title">Создание заведения</h2>
            </div>
            <button class="modal-close" @click="closeCreateVenueModal">×</button>
          </div>

          <form class="role-form" @submit.prevent="submitCreateVenue">
            <div v-if="createVenueError" class="form-alert error">
              {{ createVenueError }}
            </div>

            <div v-if="createVenueSuccess" class="form-alert success">
              {{ createVenueSuccess }}
            </div>

            <div class="form-grid">
              <label class="form-field">
                <span>Название *</span>
                <input
                  v-model.trim="createVenueForm.name"
                  type="text"
                  placeholder="Новый ресторан"
                  required
                  :disabled="isCreatingVenue"
                />
              </label>

              <label class="form-field">
                <span>Таймзона *</span>
                <input
                  v-model.trim="createVenueForm.timezone"
                  type="text"
                  placeholder="Asia/Vladivostok"
                  required
                  :disabled="isCreatingVenue"
                />
              </label>

              <label class="form-field form-field-full">
                <span>Адрес *</span>
                <input
                  v-model.trim="createVenueForm.address"
                  type="text"
                  placeholder="г. Владивосток, ул. Пример, 1"
                  required
                  :disabled="isCreatingVenue"
                />
              </label>

              <label class="form-field form-field-full checkbox-field">
                <input
                  v-model="createVenueForm.is_active"
                  type="checkbox"
                  :disabled="isCreatingVenue"
                />
                <span>Заведение активно</span>
              </label>
            </div>

            <div class="form-actions">
              <button
                type="button"
                class="wide-button secondary"
                :disabled="isCreatingVenue"
                @click="closeCreateVenueModal"
              >
                Отмена
              </button>
              <button
                type="submit"
                class="wide-button"
                :disabled="isCreatingVenue"
              >
                {{ isCreatingVenue ? createVenueLoadingLabel : createVenueSubmitLabel }}
              </button>
            </div>
          </form>
        </div>
      </div>
    </transition>
  </div>
</template>

<script>
import '../assets/cabinet.css'
import api from '../api'
import NotificationBell from '../components/NotificationBell.vue'
import ThemedSelect from '../components/ThemedSelect.vue'
import logoSupra from '../assets/Logo_supra.png'
import { fetchCurrentUser, logoutUser } from '../services/auth'
import { runForecastPipeline, uploadHistoricalForecastFile } from '../services/forecast'

const ROLE_LABELS = {
  admin: 'Администратор',
  manager: 'Менеджер',
  employee_noob: 'Официант-стажер',
  employee_pro: 'Официант-профи'
}

const getDefaultCreateRoleForm = () => ({
  username: '',
  password: '',
  password_confirm: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'employee_noob',
  venue: '',
  venue_name: ''
})

const getDefaultCreateVenueForm = () => ({
  name: '',
  address: '',
  timezone: 'Asia/Vladivostok',
  is_active: true
})

const getDefaultManageEmployeeForm = () => ({
  id: null,
  username: '',
  email: '',
  first_name: '',
  last_name: '',
  phone: '',
  role: 'employee_noob',
  venue: ''
})

const asArray = (payload) => {
  if (Array.isArray(payload)) {
    return payload
  }

  if (Array.isArray(payload?.results)) {
    return payload.results
  }

  if (Array.isArray(payload?.items)) {
    return payload.items
  }

  if (Array.isArray(payload?.data)) {
    return payload.data
  }

  return []
}

const normalizeRole = (role) => String(role || '').toLowerCase()

const getVenueId = (entity) => {
  const raw = entity?.venue_id ?? entity?.venue?.id ?? entity?.venue
  return raw === undefined || raw === null || raw === '' ? null : Number(raw)
}

export default {
  name: 'CabinetView',
  components: {
    NotificationBell,
    ThemedSelect
  },
  data() {
    let savedUser = null

    try {
      savedUser = JSON.parse(localStorage.getItem('user') || 'null')
    } catch (error) {
      savedUser = null
    }

    return {
      menuOpen: false,
      logoSupra,
      showEmployeesModal: false,
      showManageEmployeeModal: false,
      showCreateRoleModal: false,
      showCreateVenueModal: false,
      showUploadDataModal: false,
      isLoadingEmployees: false,
      isLoadingManagedEmployee: false,
      isCreatingRole: false,
      isCreatingVenue: false,
      isUploadingForecastData: false,
      isRunningForecastPipeline: false,
      isSavingManagedEmployee: false,
      employeesError: '',
      manageEmployeeError: '',
      manageEmployeeSuccess: '',
      createRoleError: '',
      createRoleSuccess: '',
      createVenueError: '',
      createVenueSuccess: '',
      forecastRunError: '',
      forecastRunSuccess: '',
      uploadDataError: '',
      uploadDataSuccess: '',
      copyNotice: '',
      createVenueSubmitLabel: '\u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0437\u0430\u0432\u0435\u0434\u0435\u043d\u0438\u0435',
      createVenueLoadingLabel: '\u0421\u043e\u0437\u0434\u0430\u0435\u043c...',
      employees: [],
      venues: [],
      forecastUploadVenueId: '',
      forecastUploadFile: null,
      forecastUploadFileName: '',
      forecastUploadPreview: [],
      managedEmployeeOriginal: null,
      createRoleForm: getDefaultCreateRoleForm(),
      manageEmployeeForm: getDefaultManageEmployeeForm(),
      createVenueForm: getDefaultCreateVenueForm(),
      user: savedUser || {
        username: '',
        email: '',
        first_name: '',
        last_name: '',
        phone: '',
        role: '',
        venue: '',
        venue_name: ''
      }
    }
  },
  computed: {
    currentUserRole() {
      return normalizeRole(this.user.role)
    },
    canManagePeople() {
      return this.currentUserRole === 'manager' || this.currentUserRole === 'admin'
    },
    currentVenueId() {
      return getVenueId(this.user)
    },
    currentVenueLabel() {
      return this.getVenueLabel(this.user)
    },
    roleRu() {
      return ROLE_LABELS[this.currentUserRole] || this.user.role || 'Не указано'
    },
    availableRoleOptions() {
      if (this.currentUserRole === 'manager') {
        return [
          { value: 'employee_noob', label: ROLE_LABELS.employee_noob },
          { value: 'employee_pro', label: ROLE_LABELS.employee_pro }
        ]
      }

      if (this.currentUserRole === 'admin') {
        return [
          { value: 'employee_noob', label: ROLE_LABELS.employee_noob },
          { value: 'employee_pro', label: ROLE_LABELS.employee_pro },
          { value: 'manager', label: ROLE_LABELS.manager },
          { value: 'admin', label: ROLE_LABELS.admin }
        ]
      }

      return []
    },
    visibleEmployees() {
      const normalizedEmployees = this.employees.filter((employee) => {
        const role = normalizeRole(employee.role)
        return ['admin', 'manager', 'employee_noob', 'employee_pro'].includes(role)
      })

      if (this.currentUserRole === 'admin') {
        return normalizedEmployees
      }

      if (
        this.currentUserRole === 'manager' ||
        this.currentUserRole === 'employee_noob' ||
        this.currentUserRole === 'employee_pro'
      ) {
        return normalizedEmployees.filter(
          (employee) =>
            normalizeRole(employee.role) === 'admin' ||
            (getVenueId(employee) !== null && getVenueId(employee) === this.currentVenueId)
        )
      }

      return []
    },
    groupedEmployees() {
      const groups = {
        admin: [],
        manager: [],
        employee_noob: [],
        employee_pro: []
      }

      this.visibleEmployees.forEach((employee) => {
        const role = normalizeRole(employee.role)

        if (groups[role]) {
          groups[role].push(employee)
        }
      })

      Object.keys(groups).forEach((key) => {
        groups[key].sort((left, right) =>
          this.getEmployeeFullName(left).localeCompare(this.getEmployeeFullName(right), 'ru')
        )
      })

      return groups
    },
    employeeSections() {
      return [
        { key: 'admin', title: 'Администраторы', items: this.groupedEmployees.admin },
        { key: 'manager', title: 'Менеджеры', items: this.groupedEmployees.manager },
        { key: 'employee_noob', title: 'Официанты-стажеры', items: this.groupedEmployees.employee_noob },
        { key: 'employee_pro', title: 'Официанты-профи', items: this.groupedEmployees.employee_pro }
      ]
    },
    venueOptions() {
      return this.venues.map((venue) => ({
        value: venue.id,
        label: venue.venue_name || venue.name || `Заведение #${venue.id}`
      }))
    },
    manageVenueOptions() {
      return [
        { value: '', label: 'Без заведения' },
        ...this.venueOptions
      ]
    },
    forecastVenueOptions() {
      return [
        { value: '', label: 'Из файла или не указывать' },
        ...this.venueOptions
      ]
    }
  },
  async mounted() {
    try {
      const freshUser = await fetchCurrentUser()
      this.user = freshUser
      localStorage.setItem('user', JSON.stringify(freshUser))
    } catch (error) {
      const savedUser = localStorage.getItem('user')

      if (savedUser) {
        try {
          this.user = JSON.parse(savedUser)
        } catch (parseError) {
          console.error('Ошибка чтения user из localStorage', parseError)
        }
      } else {
        console.error('Не удалось получить пользователя с бэка', error)
      }
    }

    if (this.currentUserRole === 'admin') {
      await this.loadVenues()
    }
  },
  beforeUnmount() {
    if (this.copyNoticeTimer) {
      clearTimeout(this.copyNoticeTimer)
    }
  },
  methods: {
    getRoleLabel(role) {
      return ROLE_LABELS[normalizeRole(role)] || role || 'Не указано'
    },
    getEmployeeFullName(employee) {
      const fullName = [employee?.first_name, employee?.last_name].filter(Boolean).join(' ').trim()
      return fullName || employee?.username || 'Без имени'
    },
    canAdminManageEmployee(employee) {
      return this.currentUserRole === 'admin' && Boolean(employee?.id)
    },
    getVenueLabel(entity) {
      return (
        entity?.venue_name ||
        entity?.venue?.venue_name ||
        entity?.venue?.name ||
        (getVenueId(entity) !== null ? `Заведение #${getVenueId(entity)}` : 'Не указано')
      )
    },
    async loadVenues() {
      try {
        const response = await api.get('/venues/')
        this.venues = asArray(response.data)
      } catch (error) {
        console.error('Не удалось загрузить заведения', error)
        this.venues = []
      }
    },
    async loadEmployees() {
      this.isLoadingEmployees = true
      this.employeesError = ''

      try {
        const response = await api.get('/users/')
        this.employees = asArray(response.data)
      } catch (error) {
        this.employees = []
        this.employeesError = this.extractErrorMessage(error, 'Не удалось загрузить сотрудников')
      } finally {
        this.isLoadingEmployees = false
      }
    },
    openMenu() {
      this.menuOpen = true
    },
    closeMenu() {
      this.menuOpen = false
    },
    goToProfile() {
      this.menuOpen = false
      this.$router.push('/cabinet')
    },
    goToSchedule() {
      this.menuOpen = false
      this.$router.push('/schedule')
    },
    async handleLogout() {
      this.menuOpen = false
      await logoutUser()
      this.$router.replace('/login')
    },
    async openEmployeesModal() {
      this.showEmployeesModal = true
      await this.loadEmployees()
    },
    closeEmployeesModal() {
      if (this.isLoadingEmployees) {
        return
      }

      this.showEmployeesModal = false
      this.employeesError = ''
    },
    async openManageEmployeeModal(employee) {
      if (!this.canAdminManageEmployee(employee)) {
        return
      }

      this.showManageEmployeeModal = true
      this.isLoadingManagedEmployee = true
      this.manageEmployeeError = ''
      this.manageEmployeeSuccess = ''
      this.managedEmployeeOriginal = null
      this.manageEmployeeForm = getDefaultManageEmployeeForm()

      try {
        if (!this.venues.length) {
          await this.loadVenues()
        }

        const response = await api.get(`/users/${employee.id}/`)
        const payload = response?.data || employee
        const venueId = getVenueId(payload)
        const normalizedRole = normalizeRole(payload.role) || 'employee_noob'

        this.managedEmployeeOriginal = {
          id: payload.id,
          username: payload.username || '',
          email: payload.email || '',
          first_name: payload.first_name || '',
          last_name: payload.last_name || '',
          phone: payload.phone || '',
          role: normalizedRole,
          venue: venueId === null ? '' : venueId
        }

        this.manageEmployeeForm = {
          ...this.managedEmployeeOriginal
        }
      } catch (error) {
        this.manageEmployeeError = this.extractErrorMessage(error, 'Не удалось загрузить сотрудника')
      } finally {
        this.isLoadingManagedEmployee = false
      }
    },
    closeManageEmployeeModal() {
      if (this.isSavingManagedEmployee || this.isLoadingManagedEmployee) {
        return
      }

      this.showManageEmployeeModal = false
      this.manageEmployeeError = ''
      this.manageEmployeeSuccess = ''
      this.managedEmployeeOriginal = null
      this.manageEmployeeForm = getDefaultManageEmployeeForm()
    },
    openCreateRoleModal() {
      this.createRoleError = ''
      this.createRoleSuccess = ''
      this.copyNotice = ''

      this.createRoleForm = {
        ...getDefaultCreateRoleForm(),
        venue: this.currentVenueId || '',
        venue_name: this.currentVenueLabel
      }

      if (this.currentUserRole === 'manager') {
        this.createRoleForm.role = 'employee_noob'
      }

      this.showCreateRoleModal = true
    },
    closeCreateRoleModal() {
      if (this.isCreatingRole) {
        return
      }

      this.showCreateRoleModal = false
      this.createRoleError = ''
      this.createRoleSuccess = ''
      this.copyNotice = ''
    },
    openCreateVenueModal() {
      this.createVenueError = ''
      this.createVenueSuccess = ''
      this.createVenueForm = getDefaultCreateVenueForm()
      this.showCreateVenueModal = true
    },
    closeCreateVenueModal() {
      if (this.isCreatingVenue) {
        return
      }

      this.showCreateVenueModal = false
      this.createVenueError = ''
      this.createVenueSuccess = ''
      this.createVenueForm = getDefaultCreateVenueForm()
    },
    openUploadDataModal() {
      this.showUploadDataModal = true
      this.uploadDataError = ''
      this.uploadDataSuccess = ''
      this.forecastUploadFile = null
      this.forecastUploadFileName = ''
      this.forecastUploadPreview = []
      this.forecastUploadVenueId = ''
    },
    closeUploadDataModal() {
      if (this.isUploadingForecastData) {
        return
      }

      this.showUploadDataModal = false
      this.uploadDataError = ''
      this.uploadDataSuccess = ''
      this.forecastUploadFile = null
      this.forecastUploadFileName = ''
      this.forecastUploadPreview = []
      this.forecastUploadVenueId = ''
    },
    getTrainingVenueId() {
      if (this.currentVenueId !== null && this.currentVenueId !== undefined && this.currentVenueId !== '') {
        return Number(this.currentVenueId)
      }

      const firstVenueId = this.venueOptions[0]?.value

      if (firstVenueId !== null && firstVenueId !== undefined && firstVenueId !== '') {
        return Number(firstVenueId)
      }

      return null
    },
    async runAdminModelTraining() {
      if (this.currentUserRole !== 'admin' || this.isRunningForecastPipeline) {
        return
      }

      const venueId = this.getTrainingVenueId()

      if (!Number.isFinite(venueId)) {
        this.forecastRunError = 'Не удалось определить заведение для обучения модели'
        this.forecastRunSuccess = ''
        return
      }

      this.isRunningForecastPipeline = true
      this.forecastRunError = ''
      this.forecastRunSuccess = ''

      try {
        const response = await runForecastPipeline({
          venue: venueId,
          processData: true,
          trainModel: true,
          makeForecast: false,
          evaluate: true
        })

        const runId = response?.id ? ` Запуск #${response.id}.` : ''
        this.forecastRunSuccess = `Обучение модели запущено.${runId}`
      } catch (error) {
        this.forecastRunError = error?.message || 'Не удалось запустить обучение модели'
      } finally {
        this.isRunningForecastPipeline = false
      }
    },
    async handleForecastFileChange(event) {
      const file = event?.target?.files?.[0]

      this.uploadDataError = ''
      this.uploadDataSuccess = ''
      this.forecastUploadFile = file || null
      this.forecastUploadFileName = file?.name || ''
      this.forecastUploadPreview = []

      if (!file) {
        return
      }
    },
    parseForecastJson(content) {
      const parsed = JSON.parse(content)

      if (Array.isArray(parsed)) {
        return parsed
      }

      if (Array.isArray(parsed?.data)) {
        return parsed.data
      }

      if (Array.isArray(parsed?.items)) {
        return parsed.items
      }

      if (parsed && typeof parsed === 'object') {
        return [parsed]
      }

      return []
    },
    parseForecastCsv(content) {
      const rows = String(content || '')
        .split(/\r?\n/)
        .map((line) => line.trim())
        .filter(Boolean)

      if (rows.length < 2) {
        return []
      }

      const firstRow = rows[0].replace(/^\uFEFF/, '')
      const delimiter = firstRow.includes(';') ? ';' : firstRow.includes('\t') ? '\t' : ','
      const headers = firstRow.split(delimiter).map((cell) => cell.trim())

      return rows.slice(1).map((row) => {
        const values = row.split(delimiter).map((cell) => cell.trim())
        return headers.reduce((accumulator, header, index) => {
          accumulator[header] = values[index] ?? ''
          return accumulator
        }, {})
      })
    },
    getRecordValue(record, keys = []) {
      for (const key of keys) {
        if (record[key] !== undefined && record[key] !== null && String(record[key]).trim() !== '') {
          return record[key]
        }
      }

      return ''
    },
    normalizeForecastDate(rawValue) {
      const value = String(rawValue || '').trim()

      if (!value) {
        return ''
      }

      const datePart = value.includes(' ') ? value.split(' ')[0] : value

      if (/^\d{4}-\d{2}-\d{2}$/.test(datePart)) {
        return datePart
      }

      if (/^\d{2}\.\d{2}\.\d{4}$/.test(datePart)) {
        const [day, month, year] = datePart.split('.')
        return `${year}-${month}-${day}`
      }

      if (/^\d{2}\/\d{2}\/\d{4}$/.test(datePart)) {
        const [day, month, year] = datePart.split('/')
        return `${year}-${month}-${day}`
      }

      return datePart
    },
    parseForecastLoad(rawValue) {
      const value = String(rawValue ?? '').trim()

      if (!value) {
        return Number.NaN
      }

      const normalized = value
        .replace(/\s/g, '')
        .replace(/,/g, '')
        .replace(/[^\d.-]/g, '')

      return Number(normalized)
    },
    normalizeForecastRecord(record) {
      if (!record || typeof record !== 'object') {
        return null
      }

      const rawDate = this.getRecordValue(record, [
        'date',
        'day',
        'shift_date',
        'Учетный день',
        'учетный день',
        'Дата',
        'дата'
      ])
      const date = this.normalizeForecastDate(rawDate)

      const rawLoad = this.getRecordValue(record, [
        'load',
        'actual_load',
        'predicted_load',
        'value',
        'Количество гостей',
        'количество гостей',
        'заказов',
        'Заказов'
      ])
      const load = this.parseForecastLoad(rawLoad)

      const rawVenue = record.venue ?? record.venue_id ?? this.forecastUploadVenueId ?? ''
      const venue = rawVenue === '' || rawVenue === null || rawVenue === undefined ? null : Number(rawVenue)

      if (!date || !Number.isFinite(load)) {
        return null
      }

      const normalized = {
        date,
        load
      }

      if (Number.isFinite(venue)) {
        normalized.venue = venue
        normalized.venue_id = venue
      }

      return normalized
    },
    async submitForecastDataUpload() {
      if (!this.forecastUploadFile) {
        this.uploadDataError = 'Сначала выберите файл'
        return
      }

      const defaultVenueId = this.forecastUploadVenueId ? Number(this.forecastUploadVenueId) : null

      this.isUploadingForecastData = true
      this.uploadDataError = ''
      this.uploadDataSuccess = ''

      try {
        const response = await uploadHistoricalForecastFile(this.forecastUploadFile, {
          venueId: Number.isFinite(defaultVenueId) ? defaultVenueId : null
        })
        const savedCount =
          Number(response?.created) ||
          Number(response?.count) ||
          Number(response?.created_count) ||
          Number(response?.saved) ||
          0

        this.uploadDataSuccess = savedCount
          ? `Данные загружены в БД. Сохранено записей: ${savedCount}.`
          : 'Файл отправлен в БД.'
      } catch (error) {
        this.uploadDataError = error?.message || 'Не удалось загрузить данные в БД'
      } finally {
        this.isUploadingForecastData = false
      }
    },
    buildCreateRolePayload() {
      const payload = {
        username: this.createRoleForm.username,
        password: this.createRoleForm.password,
        password_confirm: this.createRoleForm.password_confirm,
        email: this.createRoleForm.email,
        first_name: this.createRoleForm.first_name,
        last_name: this.createRoleForm.last_name,
        phone: this.createRoleForm.phone || undefined,
        role: this.createRoleForm.role || 'employee_noob'
      }

      if (this.currentUserRole === 'admin') {
        if (this.createRoleForm.venue) {
          payload.venue = Number(this.createRoleForm.venue)
        }
      } else if (this.currentUserRole === 'manager' && this.currentVenueId !== null) {
        payload.venue = this.currentVenueId
      }

      return payload
    },
    buildCreateVenuePayload() {
      const name = this.createVenueForm.name.trim()
      const address = this.createVenueForm.address.trim()
      const timezone = this.createVenueForm.timezone.trim()

      return {
        name,
        address,
        timezone,
        is_active: this.createVenueForm.is_active
      }
    },
    buildManageEmployeePayload() {
      const payload = {
        username: this.manageEmployeeForm.username.trim(),
        email: this.manageEmployeeForm.email.trim(),
        first_name: this.manageEmployeeForm.first_name.trim(),
        last_name: this.manageEmployeeForm.last_name.trim(),
        phone: this.manageEmployeeForm.phone.trim(),
        role: this.manageEmployeeForm.role || 'employee_noob'
      }

      if (this.manageEmployeeForm.venue !== '' && this.manageEmployeeForm.venue !== null && this.manageEmployeeForm.venue !== undefined) {
        payload.venue = Number(this.manageEmployeeForm.venue)
      } else {
        payload.venue = null
      }

      return payload
    },
    extractErrorMessage(error, fallbackMessage = 'Не удалось выполнить запрос') {
      const data = error?.response?.data
      const status = Number(error?.response?.status)

      if (!data) {
        return error?.message || fallbackMessage
      }

      if (typeof data === 'string') {
        const normalized = data.trim()

        if (/^<!doctype html/i.test(normalized) || /^<html/i.test(normalized)) {
          const titleMatch = normalized.match(/<title>(.*?)<\/title>/i)
          const title = titleMatch?.[1]?.trim()

          if (status === 404) {
            return title
              ? `Сервер не нашел нужный маршрут: ${title}.`
              : 'Сервер не нашел нужный маршрут.'
          }

          if (status === 405) {
            return title
              ? `Сервер отклонил метод запроса: ${title}.`
              : 'Сервер отклонил метод запроса.'
          }

          return title
            ? `${fallbackMessage}. ${title}.`
            : fallbackMessage
        }

        return data
      }

      if (data.detail) {
        return Array.isArray(data.detail) ? data.detail.join(', ') : data.detail
      }

      return (
        Object.entries(data)
          .map(([key, value]) => {
            const normalizedValue = Array.isArray(value) ? value.join(', ') : value
            return `${key}: ${normalizedValue}`
          })
          .join('; ') || fallbackMessage
      )
    },
    async copyText(value, successMessage) {
      if (!value) {
        return
      }

      try {
        await navigator.clipboard.writeText(String(value))
        this.showCopyNotice(successMessage)
      } catch (error) {
        this.showCopyNotice('Не удалось скопировать')
      }
    },
    async copyCredentials() {
      const username = this.createRoleForm.username?.trim()
      const password = this.createRoleForm.password

      if (!username || !password) {
        return
      }

      const payload = `Логин: ${username}\nПароль: ${password}`
      await this.copyText(payload, 'Логин и пароль скопированы')
    },
    showCopyNotice(message) {
      this.copyNotice = message

      if (this.copyNoticeTimer) {
        clearTimeout(this.copyNoticeTimer)
      }

      this.copyNoticeTimer = setTimeout(() => {
        this.copyNotice = ''
      }, 1800)
    },
    async submitCreateRole() {
      this.createRoleError = ''
      this.createRoleSuccess = ''

      if (this.createRoleForm.password !== this.createRoleForm.password_confirm) {
        this.createRoleError = 'Пароли должны совпадать'
        return
      }

      this.isCreatingRole = true

      try {
        await api.post('/auth/register/', this.buildCreateRolePayload())
        this.createRoleSuccess = 'Сотрудник успешно создан'
        this.createRoleForm = {
          ...getDefaultCreateRoleForm(),
          venue:
            this.currentUserRole === 'manager'
              ? this.currentVenueId || ''
              : this.currentUserRole === 'admin'
                ? ''
                : '',
          venue_name:
            this.currentUserRole === 'manager'
              ? this.currentVenueLabel
              : ''
        }

        if (this.currentUserRole === 'manager') {
          this.createRoleForm.role = 'employee_noob'
        }

        if (this.showEmployeesModal) {
          await this.loadEmployees()
        }
      } catch (error) {
        this.createRoleError = this.extractErrorMessage(error, 'Не удалось создать сотрудника')
      } finally {
        this.isCreatingRole = false
      }
    },
    async submitCreateVenue() {
      this.createVenueError = ''
      this.createVenueSuccess = ''

      if (!this.createVenueForm.name.trim()) {
        this.createVenueError = 'Название заведения обязательно'
        return
      }

      if (!this.createVenueForm.address.trim()) {
        this.createVenueError = 'Адрес заведения обязателен'
        return
      }

      if (!this.createVenueForm.timezone.trim()) {
        this.createVenueError = 'Таймзона обязательна'
        return
      }

      this.isCreatingVenue = true

      try {
        await api.post('/venues/create/', this.buildCreateVenuePayload())
        this.createVenueSuccess = 'Заведение успешно создано'
        this.createVenueForm = getDefaultCreateVenueForm()
        await this.loadVenues()
      } catch (error) {
        this.createVenueError = this.extractErrorMessage(error, 'Не удалось создать заведение')
      } finally {
        this.isCreatingVenue = false
      }
    },
    async submitManageEmployee() {
      if (!this.manageEmployeeForm.id || this.currentUserRole !== 'admin') {
        return
      }

      this.manageEmployeeError = ''
      this.manageEmployeeSuccess = ''
      this.isSavingManagedEmployee = true

      try {
        await api.patch(`/users/${this.manageEmployeeForm.id}/`, this.buildManageEmployeePayload())

        if (Number(this.manageEmployeeForm.id) === Number(this.user?.id)) {
          const freshUser = await fetchCurrentUser()
          this.user = freshUser
          localStorage.setItem('user', JSON.stringify(freshUser))
        }

        await this.loadEmployees()
        this.manageEmployeeSuccess = 'Данные сотрудника обновлены'
        this.managedEmployeeOriginal = {
          ...this.manageEmployeeForm,
          role: normalizeRole(this.manageEmployeeForm.role)
        }
      } catch (error) {
        this.manageEmployeeError = this.extractErrorMessage(error, 'Не удалось обновить сотрудника')
      } finally {
        this.isSavingManagedEmployee = false
      }
    }
  }
}
</script>





