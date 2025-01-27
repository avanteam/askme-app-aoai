import CryptoJS from 'crypto-js';

// Fonction pour obtenir la clé de chiffrement
function getEncryptionKey() {
  const keyBase64 = '+gSxYLZWesSFOppNJg1v7K7VvK4JzbxrLGPH+C6Ettc=';
  return CryptoJS.enc.Base64.parse(keyBase64);
}

// Fonction de chiffrement
export function encryptString(plainText:string) {
  const key = getEncryptionKey();
  const iv = CryptoJS.lib.WordArray.random(16); // Générer un IV de 16 octets

  // Chiffrement avec AES
  const encrypted = CryptoJS.AES.encrypt(plainText, key, {
    iv: iv,
    mode: CryptoJS.mode.CBC,
    padding: CryptoJS.pad.Pkcs7,
  });

  // Combiner IV et données chiffrées
  const combined = iv.concat(encrypted.ciphertext);

  // Convertir en Base64
  return CryptoJS.enc.Base64.stringify(combined);
}

// // Fonction de déchiffrement
// export function decryptString(encryptedBase64:string) {
//   const key = getEncryptionKey();

//   // Décoder les données en Base64
//   const combined = CryptoJS.enc.Base64.parse(encryptedBase64);

//   // Extraire l'IV (les 16 premiers octets) et les données chiffrées
//   const iv = CryptoJS.lib.WordArray.create(combined.words.slice(0, 4), 16); // IV = 16 octets
//   const ciphertext = CryptoJS.lib.WordArray.create(
//     combined.words.slice(4),
//     combined.sigBytes - 16
//   );

//   // Déchiffrement avec AES
//   const decrypted = CryptoJS.AES.decrypt(
//     { ciphertext: ciphertext },
//     key,
//     {
//       iv: iv,
//       mode: CryptoJS.mode.CBC,
//       padding: CryptoJS.pad.Pkcs7,
//     }
//   );

//   // Convertir en texte clair
//   return decrypted.toString(CryptoJS.enc.Utf8);
// }
