const GENERIC = "We couldn't complete that. Please try again.";
const FIELD_LABELS = {
  username: "Username", email: "Email address", first_name: "First name", last_name: "Last name",
  name: "Name", role: "Role", password: "Password", current_password: "Current password",
  new_password: "New password", confirm_password: "Password confirmation", category: "Category",
  title: "Expense name", department: "Department", branch: "Branch", due_date: "Date", currency: "Currency",
  items: "Line items", description: "Particular", quantity: "Quantity", unit_price: "Unit cost",
  text: "Comment", comment: "Comment", file: "File", label: "Invoice title", is_active: "Account status",
};

// Only fixed application wording is displayed. Never echo server payloads,
// request URLs, stack traces or arbitrary exception messages into the UI.
function validationMessage(value) {
  if (typeof value !== "string") return null;
  const rules = [
    [/current password is incorrect/i, "Your current password is incorrect."],
    [/passwords do not match/i, "The passwords do not match."],
    [/different from your current password/i, "Choose a different password."],
    [/password.*too short|at least 8 characters/i, "Use a password with at least 8 characters."],
    [/password.*too common/i, "Choose a less common password."],
    [/password.*entirely numeric/i, "Use a mix of letters and numbers in your password."],
    [/password.*too similar/i, "Choose a password that differs from your personal details."],
    [/email address|valid email/i, "Enter a valid email address."],
    [/this field is required|may not be blank|may not be null|must not be blank/i, "This field is required."],
    [/already exists|must be unique|username conflict/i, "This value is already in use."],
    [/only one active approver|there can be only one active approver|active approver already exists/i, "An active approver already exists. Update the existing account instead."],
    [/no active approver/i, "Ask an administrator to assign an approver before submitting."],
    [/comment.*required|reason.*required/i, "Add a comment before continuing."],
    [/at least one item/i, "Add at least one line item."],
    [/enter an expense name/i, "Enter an expense name before submitting."],
    [/valid department and branch/i, "Select a department and branch."],
    [/greater than or equal to 0|negative|nonnegative/i, "Use zero or a positive amount."],
    [/valid number|valid integer|decimal places|digits in total|decimal.*places/i, "Enter a valid number within the allowed range."],
    [/valid date|date.*format/i, "Choose a valid date."],
    [/valid choice|not a valid choice/i, "Choose one of the available options."],
    [/no more than .*characters|at most .*characters|too long/i, "This entry is too long. Shorten it and try again."],
    [/png|jpeg|jpg|pdf|file content|matching file/i, "Choose a supported file within the size limit shown."],
    [/maximum file size|file.*too large|10 mb|1 mb|image dimensions/i, "Choose a smaller file within the size limit shown."],
    [/empty file|file.*nonempty|empty.*file/i, "Choose a file that isn't empty."],
    [/provider rejected.*sender credentials/i, "Email delivery couldn't sign in. Check the application sender settings."],
    [/sender credentials are missing|email server is not configured|valid sender address/i, "Set up the application email sender before testing."],
    [/preview only|nothing reaches an inbox/i, "Email is in preview mode. Set up a sender to test delivery."],
    [/test could not be confirmed|test was not confirmed/i, "We couldn't confirm the test email. Check the sender settings before retrying."],
    [/cannot remove your own administrator/i, "You can't remove your own administrator access."],
    [/cannot close|cannot .*expense in/i, "This action isn't available for the expense's current status. Refresh the page."],
  ];
  return rules.find(([pattern]) => pattern.test(value))?.[1] ?? null;
}

function collectMessages(value, prefix = "", depth = 0) {
  if (depth > 4) return [];
  if (typeof value === "string") {
    const message = validationMessage(value);
    return message ? [prefix ? `${prefix}: ${message}` : message] : [];
  }
  if (Array.isArray(value)) return value.slice(0, 5).flatMap((entry, index) => collectMessages(entry,
    entry && typeof entry === "object" && !Array.isArray(entry) ? `${prefix || "Item"} ${index + 1}` : prefix, depth + 1));
  if (value && typeof value === "object") return Object.entries(value).slice(0, 20).flatMap(([field, entry]) => {
    if (field === "detail" || field === "non_field_errors") return collectMessages(entry, prefix, depth + 1);
    const label = FIELD_LABELS[field];
    return label ? collectMessages(entry, prefix ? `${prefix} - ${label}` : label, depth + 1) : [];
  });
  return [];
}

export function fieldErrors(error) {
  if (error?.response?.status !== 400) return {};
  const data = error.response.data;
  if (!data || typeof data !== "object" || Array.isArray(data)) return {};
  return Object.fromEntries(Object.entries(data).filter(([field]) => field in FIELD_LABELS || field === "non_field_errors")
    .map(([field, value]) => [field, [...new Set(collectMessages(value))]])
    .filter(([, messages]) => messages.length));
}

export function errorMessage(error) {
  if (!error || typeof error !== "object") return GENERIC;
  const status = error.response?.status;
  const login = /\/auth\/login(?:\?|$)/.test(error.config?.url ?? "");
  if (status === 401) return login ? "The username or email and password don't match. Please try again." : "Your session has expired. Please sign in again.";
  if (status === 403) return "You don't have permission to do that.";
  if (status === 404 || status === 410) return "This item is no longer available. Refresh the page to continue.";
  if (status === 409) return "This expense has changed. Refresh the page before trying again.";
  if (status === 413) return "That file is too large. Choose a smaller file.";
  if (status === 429) return login ? "Too many sign-in attempts. Please wait a few minutes before trying again." : "Please wait a little before trying again.";
  if (status >= 500) return "Homebase is temporarily unavailable. Please try again shortly.";
  if (status === 400 || status === 422) {
    const messages = [...new Set(collectMessages(error.response.data))].slice(0, 3);
    return messages.length ? messages.join(" ") : "Check the details you entered and try again.";
  }
  if (!error.response && (error.isAxiosError || error.code === "ERR_NETWORK" || error.code === "ECONNABORTED" || error.code === "ETIMEDOUT")) {
    const auth = /\/auth\/(?:login|refresh)(?:\?|$)/.test(error.config?.url ?? "");
    const write = !auth && error.config?.method && !["get", "head", "options"].includes(error.config.method.toLowerCase());
    return write ? "We couldn't confirm the change. Check your connection and the latest status before trying again." : "We couldn't reach Homebase. Check your connection and try again.";
  }
  return GENERIC;
}

export function retryQuery(failureCount, error) {
  const status = error?.response?.status;
  return failureCount < 1 && (!status || status >= 500);
}
