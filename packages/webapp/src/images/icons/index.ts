/// <reference types="vite-plugin-svgr/client" />
import FacebookImg from './facebook.svg?react';
import GoogleImg from './google.svg?react';
import { makeIcon } from './makeIcon';
import SignetImg from './signet.svg?react';
import WordmarkImg from './wordmark.svg?react';

//<-- IMPORT ICON FILE -->

export const FacebookIcon = makeIcon(FacebookImg);
export const GoogleIcon = makeIcon(GoogleImg);
export const SignetIcon = makeIcon(SignetImg);
export const WordmarkIcon = makeIcon(WordmarkImg);
//<-- EXPORT ICON COMPONENT -->
