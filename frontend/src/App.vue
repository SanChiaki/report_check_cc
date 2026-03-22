<template>
  <div id="app">
    <nav class="navbar">
      <div class="nav-brand">报告一致性检查</div>
      <div class="nav-links">
        <router-link to="/">提交检查</router-link>
        <router-link to="/rules">规则配置</router-link>
      </div>
    </nav>
    <main class="main-content">
      <router-view />
    </main>
  </div>
</template>

<style>
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e8ecf0;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}

.nav-brand {
  font-size: 18px;
  font-weight: 600;
  color: #1a1a2e;
}

.nav-links {
  display: flex;
  gap: 24px;
}

.nav-links a {
  font-size: 14px;
  color: #666;
  padding: 4px 0;
  border-bottom: 2px solid transparent;
  transition: color 0.2s, border-color 0.2s;
}

.nav-links a.router-link-active {
  color: #4f6ef7;
  border-bottom-color: #4f6ef7;
}

.main-content {
  max-width: 960px;
  margin: 0 auto;
  padding: 32px 24px;
}
</style>
