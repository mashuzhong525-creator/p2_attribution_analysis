<script setup>
import { ref, onMounted } from 'vue'
import { useConfigStore } from '../stores/config'
import { useDatasourceStore } from '../stores/datasource'

const cfgStore = useConfigStore()
const dsStore = useDatasourceStore()
const tab = ref('config')

const editForm = ref({ show: false, id: null, name: '', host: '', port: 3306, database: '', username: '', password: '', is_readonly: true })
const testMsg = ref('')
const saving = ref(false)

onMounted(async () => {
  try { await cfgStore.fetch() } catch (e) { window.$toast(e.message, 'error') }
  try { await dsStore.fetch() } catch (e) { window.$toast(e.message, 'error') }
})

// ---- 配置 ----
function serialize(v, type) {
  if (type === 'bool') return v === true || v === 'true' || v === '1'
  if (type === 'int') return Number(v) || 0
  if (type === 'float') return Number(v) || 0
  if (type === 'json') { try { return JSON.parse(v) } catch { return v } }
  return String(v)
}
function inputType(t) {
  if (t === 'bool') return 'checkbox'
  if (t === 'int' || t === 'float') return 'number'
  return 'text'
}
async function saveConfig(group) {
  saving.value = true
  try {
    const items = group.items.map((i) => ({
      config_key: i.config_key,
      config_value: serialize(i.config_value, i.config_type)
    }))
    await cfgStore.update(items)
    window.$toast(`「${group.group}」配置已保存并热加载`, 'success')
  } catch (e) {
    window.$toast(e.message, 'error')
  } finally { saving.value = false }
}

// ---- 数据源 ----
function openEdit(ds) {
  editForm.value = ds ? {
    show: true, id: ds.id, name: ds.name, host: ds.host, port: ds.port,
    database: ds.database, username: ds.username, password: '', is_readonly: ds.is_readonly
  } : { show: true, id: null, name: '', host: '', port: 3306, database: '', username: '', password: '', is_readonly: true }
  testMsg.value = ''
}
async function saveDs() {
  saving.value = true
  const f = editForm.value
  const body = { name: f.name, db_type: 'mysql', host: f.host, port: Number(f.port) || 3306, database: f.database, username: f.username, password: f.password, is_readonly: f.is_readonly }
  try {
    if (f.id) await dsStore.update(f.id, body)
    else await dsStore.create(body)
    editForm.value.show = false
    window.$toast('数据源已保存', 'success')
  } catch (e) { window.$toast(e.message, 'error') }
  finally { saving.value = false }
}
async function testDs() {
  const f = editForm.value
  const body = f.id
    ? { id: f.id }
    : { host: f.host, port: Number(f.port) || 3306, database: f.database, username: f.username, password: f.password }
  try {
    const r = await dsStore.test(body)
    testMsg.value = r.message
    window.$toast(r.message, r.ok ? 'success' : 'error')
  } catch (e) { testMsg.value = e.message }
}
async function removeDs(id, name) {
  if (!confirm(`确认删除数据源「${name}」？`)) return
  try { await dsStore.remove(id); window.$toast('已删除', 'success') }
  catch (e) { window.$toast(e.message, 'error') }
}
</script>

<template>
  <div class="admin-wrap">
    <div class="tabs">
      <button class="tab" :class="{ on: tab === 'config' }" @click="tab = 'config'">系统配置</button>
      <button class="tab" :class="{ on: tab === 'datasource' }" @click="tab = 'datasource'">数据源</button>
    </div>

    <!-- 配置 Tab -->
    <div v-if="tab === 'config'" class="cfg-panel">
      <div v-for="g in cfgStore.groups" :key="g.group" class="cfg-group">
        <div class="cfg-group-head">
          <h3>{{ g.group }}</h3>
          <button class="btn sm" :disabled="saving" @click="saveConfig(g)">保存本组</button>
        </div>
        <div class="cfg-row head">
          <span>键</span><span>类型</span><span>值</span><span>说明</span>
        </div>
        <div class="cfg-row" v-for="i in g.items" :key="i.config_key">
          <span class="mono">{{ i.config_key }}</span>
          <span class="muted">{{ i.config_type }}</span>
          <span>
            <input :type="inputType(i.config_type)" v-model="i.config_value"
                   :checked="i.config_type === 'bool' ? !!i.config_value : undefined" />
          </span>
          <span class="muted">{{ i.description }}</span>
        </div>
      </div>
    </div>

    <!-- 数据源 Tab -->
    <div v-else class="ds-panel">
      <div class="ds-toolbar">
        <span class="muted">预置场景库（商品/库存）为只读示例，仅 admin 可增改外部源</span>
        <button class="btn primary sm" @click="openEdit(null)">+ 新建数据源</button>
      </div>
      <table class="ds-table">
        <thead><tr><th>名称</th><th>类型</th><th>地址</th><th>库名</th><th>账号</th><th>只读</th><th>启用</th><th>操作</th></tr></thead>
        <tbody>
          <tr v-for="d in dsStore.list" :key="d.id">
            <td>{{ d.name }}</td><td>{{ d.db_type }}</td>
            <td class="mono">{{ d.host }}:{{ d.port }}</td><td class="mono">{{ d.database }}</td>
            <td>{{ d.username }}</td>
            <td>{{ d.is_readonly ? '是' : '否' }}</td><td>{{ d.is_enabled ? '启用' : '停用' }}</td>
            <td>
              <button class="btn sm" @click="openEdit(d)">编辑</button>
              <button class="btn sm danger" @click="removeDs(d.id, d.name)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 数据源编辑弹窗 -->
    <div v-if="editForm.show" class="modal-mask" @click.self="editForm.show = false">
      <div class="modal">
        <h3>{{ editForm.id ? '编辑数据源' : '新建数据源' }}</h3>
        <div class="form-grid">
          <label>名称<input v-model="editForm.name" /></label>
          <label>主机<input v-model="editForm.host" placeholder="localhost" /></label>
          <label>端口<input type="number" v-model="editForm.port" /></label>
          <label>库名<input v-model="editForm.database" /></label>
          <label>账号<input v-model="editForm.username" /></label>
          <label>密码<input type="password" v-model="editForm.password" :placeholder="editForm.id ? '留空则不修改' : ''" /></label>
          <label class="check"><input type="checkbox" v-model="editForm.is_readonly" /> 只读</label>
        </div>
        <p v-if="testMsg" class="muted">{{ testMsg }}</p>
        <div class="modal-actions">
          <button class="btn sm" @click="testDs">测试连接</button>
          <span class="spacer"></span>
          <button class="btn ghost" @click="editForm.show = false">取消</button>
          <button class="btn primary" :disabled="saving" @click="saveDs">保存</button>
        </div>
      </div>
    </div>
  </div>
</template>
