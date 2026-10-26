export function toast(message: string, isError = false) {
  const node = document.createElement("div");
  node.className = "toast" + (isError ? " err" : "");
  node.setAttribute("role", "status");
  node.textContent = message;
  document.body.append(node);
  setTimeout(() => node.remove(), 3200);
}
