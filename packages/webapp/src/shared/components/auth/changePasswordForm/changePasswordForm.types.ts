export type ChangePasswordFormFields = {
  oldPassword?: string;
  newPassword: string;
  confirmNewPassword: string;
  otpToken?: string;
};
