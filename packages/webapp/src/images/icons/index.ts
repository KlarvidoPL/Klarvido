/// <reference types="vite-plugin-svgr/client" />
import FacebookImg from './facebook.svg?react';
import GoogleImg from './google.svg?react';
import SignetImg from './signet.svg?react';
import { makeIcon } from './makeIcon';

//<-- IMPORT ICON FILE -->

export const FacebookIcon = makeIcon(FacebookImg);
export const GoogleIcon = makeIcon(GoogleImg);
export const SignetIcon = makeIcon(SignetImg);
//<-- EXPORT ICON COMPONENT -->
