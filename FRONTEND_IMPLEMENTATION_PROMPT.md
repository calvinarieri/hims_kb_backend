        "permissions": [
          { "code": "chat:manage", "label": "Manage Chat & Customer Service" },
          { "code": "feedback:manage", "label": "View & Manage User Feedback" }
        ]
      },
      {
        "category": "Products",
        "permissions": [
          { "code": "product:manage", "label": "Manage Products & Versions" }
        ]
      },
      {
        "category": "Dashboard",
        "permissions": [
          { "code": "dashboard:view", "label": "View Analytics & Dashboard" }
        ]
      }
    ]
  }
  ```
- `GET /auth/roles/`: List all existing roles.
- `POST /auth/roles/`: Create a new role.
  ```json
  {
    "name": "Clinical Manager",
    "description": "Oversees articles and staff activity",
    "permissions": ["articles:read", "articles:create", "articles:update", "dashboard:view"]
  }
  ```
- `PATCH /auth/roles/{id}/`: Update role details or assigned permissions.
- `DELETE /auth/roles/{id}/`: Delete a role.

### 2. Staff Management (`/auth/staff/`)
- `GET /auth/staff/`: List all staff users with nested `role_details`.
  ```json
  {
    "status_code": 200,
    "data": [
      {
        "id": "uuid-here",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@hims.org",
        "role": "role-uuid-here",
        "role_details": {
          "id": "role-uuid-here",
          "name": "Senior Nurse",
          "description": "Medical staff member",
          "permissions": ["articles:read", "articles:create"]
        },
        "is_active": true,
        "is_staff": true,
        "is_superuser": false
      }
    ]
  }
  ```
- `POST /auth/staff/`: Create a new staff account (**Note**: Triggers welcome email with raw password to the staff member).
  ```json
  {
    "first_name": "Alice",
    "last_name": "Smith",
    "email": "alice@hims.org",
    "password": "SecurePassword123!",
    "role": "role-uuid-here"
  }
  ```
- `PATCH /auth/staff/{id}/`: Update staff account.
  - Passing `"password": "NewPass"` triggers a password update notification email.
  - Passing `"is_active": false` deactivates/dismisses the staff member and triggers a dismissal notification email.
- `DELETE /auth/staff/{id}/`: Deletes/deactivates staff member (triggers dismissal email).

---

## 🎨 UI & Design Requirements

### Theme Palette
Use Tailwind CSS classes matching the brand palette:
- **Primary Headers & Dark Accents**: Slate-900 (`bg-slate-900`, `text-slate-900`)
- **Brand Action Accent & Badges**: Amber-700 (`bg-amber-700`, `hover:bg-amber-800`, `text-amber-700`, `border-amber-700`)
- **Card / Modal Containers**: White (`bg-white`, `border-slate-200`, `shadow-xl`)
- **Body Text**: Charcoal / Dark Slate (`text-slate-900`, `text-slate-700`)

---

## 📦 Required Components to Build

### 1. Roles & Permissions Management Page (`/admin/roles`)
- **Role List**: Display cards or table of roles showing:
  - Role Name & Description
  - Count of permissions assigned
  - Permission pills/badges
  - Edit & Delete action buttons
- **Create/Edit Role Modal**:
  - Name (text input)
  - Description (textarea)
  - **Permissions Matrix (Checkbox Groups)**:
    - Fetch categories from `GET /auth/roles/available-permissions/`.
    - Render checkboxes grouped under each category card (`Articles`, `Staff & Roles`, etc.).
    - Include a "Select All" / "Deselect All" button per category.
    - Submit formatted array of permission code strings (e.g. `["articles:read", "articles:create"]`).

### 2. Staff Management Page (`/admin/staff`)
- **Staff List Table**:
  - Full Name & Email address
  - Role Badge (e.g. "Senior Nurse")
  - Status Badge (`Active` in green/slate, `Dismissed / Inactive` in red)
  - Action menu: Edit Role, Reset Password, Dismiss Staff
- **Add Staff Modal**:
  - Inputs: First Name, Last Name, Email, Password, Role Dropdown.
  - **Info Notice Box**: Alert the admin that creating the staff user will automatically dispatch a styled welcome email containing their credentials and login instructions.
- **Admin Password Reset Modal**:
  - Modal allowing admin to enter a new password for the staff member.
  - Alert notice: Inform admin that updating password sends a security notification email to the staff user.
- **Dismiss Staff Confirmation Modal**:
  - Confirm deactivating account (`is_active = false`).
  - Alert notice: Warn admin that deactivating staff access immediately revokes privileges and sends a dismissal email notification.

### 3. Permission Guard Hook & Component
- **`useHasPermission(requiredPermission)` Hook**:
  - Reads active user from auth state (`user.role_details.permissions` or `user.is_superuser`).
  - Returns `true` if `is_superuser` is `true` OR if `permissions` contains `requiredPermission` or `*`.
- **`<Can permission="articles:create">` Component**:
  - Wraps buttons, tabs, or routes.
  - Hides wrapped elements if user lacks permission.

---

## 📋 Implementation Checklist for Developer

- [ ] Fetch available permissions on Role Modal load (`/auth/roles/available-permissions/`).
- [ ] Implement state management for permission checkbox selection array.
- [ ] Connect Add Staff form submit to `POST /auth/staff/`.
- [ ] Connect Staff Password Reset to `PATCH /auth/staff/{id}/` with `password`.
- [ ] Connect Staff Deactivation to `PATCH /auth/staff/{id}/` with `is_active: false`.
- [ ] Add visual feedback (toasts / alerts) confirming when emails are queued/sent.
- [ ] Add `useHasPermission` hook to hide unauthorized sidebar menu links (e.g. hide "Role Management" if user lacks `roles:manage`).

