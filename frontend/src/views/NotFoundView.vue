<script setup>
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="plain-page">
    <div class="big">404</div>
    <div class="desc">页面不存在或已被移动</div>
    <div class="actions">
      <button class="btn primary" @click="router.push('/')">返回工作台</button>
    </div>
  </div>
</template>
