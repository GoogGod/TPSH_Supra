<template>
  <main class="not-found">
    <section class="not-found__card">
      <p class="not-found__code">404</p>
      <h1 class="not-found__title">Страница не найдена</h1>
      <p class="not-found__text">
        Проверьте адрес или вернитесь на страницу входа.
      </p>
      <router-link to="/login" class="not-found__link">
        Перейти на логин
      </router-link>
    </section>
  </main>
</template>

<style scoped>
.not-found {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 24px;
  background: linear-gradient(180deg, #f2f5ff 0%, #ffffff 100%);
}

.not-found__card {
  width: min(520px, 100%);
  padding: 36px 28px;
  border-radius: 16px;
  background: #ffffff;
  box-shadow: 0 12px 40px rgba(16, 25, 93, 0.1);
  text-align: center;
}

.not-found__code {
  margin: 0;
  font-size: 56px;
  font-weight: 800;
  line-height: 1;
  color: #10195d;
}

.not-found__title {
  margin: 12px 0 0;
  font-size: 28px;
  line-height: 1.2;
  color: #10195d;
}

.not-found__text {
  margin: 12px 0 0;
  color: #4b557d;
  font-size: 16px;
  line-height: 1.5;
}

.not-found__link {
  display: inline-block;
  margin-top: 20px;
  padding: 10px 18px;
  border-radius: 10px;
  background: #10195d;
  color: #fff;
  text-decoration: none;
  font-weight: 600;
}

.not-found__link:hover {
  background: #0d144a;
}
</style>
