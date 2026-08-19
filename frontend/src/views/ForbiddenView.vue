<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="plain-page">
    <div class="big warn">403</div>
    <div class="desc">您没有访问该页面的权限</div>
    <div class="sub">当前角色无权访问管理后台；如需权限请联系系统管理员</div>
    <div class="actions">
      <button class="btn primary" @click="router.push('/')">返回工作台</button>
      <button class="btn" @click="router.push('/login')">返回登录</button>
    </div>
  </div>
</template>
