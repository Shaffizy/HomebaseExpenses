import toast from "react-hot-toast";

function show(type, message, options = {}) {
  return toast[type](message, {
    duration: type === "error" ? 6000 : 3500,
    ...options,
    id: options.id ?? `${type}:${typeof message === "string" ? message : "notification"}`,
    ariaProps: { role: type === "error" ? "alert" : "status", "aria-live": type === "error" ? "assertive" : "polite" },
  });
}

export default {
  success: (message, options) => show("success", message, options),
  error: (message, options) => show("error", message, options),
  dismiss: toast.dismiss,
};
