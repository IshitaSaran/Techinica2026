// Learn Mode teaching content. Plain language, written for someone who has
// never heard these terms. Shown only in Learn Mode.

export const INTROS = {
  search: {
    icon: "🔎",
    title: "Lesson 1: How can a computer search photos by meaning?",
    body: [
      "Investigators often seize hundreds of photos with useless names like IMG_4821.jpg. Looking through them one by one takes hours. Semantic search lets you describe what you want instead, like “a beach” or “a phone”, and get the closest pictures first.",
      "It works with an AI model called CLIP, trained on millions of pictures paired with captions. CLIP turns any picture, and any sentence, into a list of 512 numbers called an embedding. Think of it as coordinates on a map of meaning. A photo of a dog and the words “a dog” land close together on that map.",
      "Sift worked out the coordinates of every evidence photo ahead of time. When you search, it only has to place your words on the map and measure which photos are nearest. That's why results come back almost instantly.",
    ],
    tryIt: "Try one of these, then press Search:",
    examples: ["shoes", "a beach", "a phone", "a forest", "a car"],
  },
  stego: {
    icon: "🫧",
    title: "Lesson 2: What is steganography?",
    body: [
      "Encryption scrambles a message so nobody can read it. Steganography hides the message so nobody knows it's there. The word comes from Greek for “covered writing.” A normal-looking holiday photo can carry a secret, and that photo is exactly what an investigator has to catch.",
      "Every pixel is made of red, green and blue values from 0 to 255. Changing a value by just 1, say from 200 to 201, is invisible to the eye. The very last binary digit of each value is called the least significant bit (LSB). By overwriting those last bits, someone can tuck thousands of bytes of data into a picture that looks completely unchanged.",
      "The bit-plane view shows only those last bits, drawn as black and white. In a natural photo they look like the image's own texture. Hidden data makes them look like TV static, and that's the tell. “Analyze” measures this with statistics, and “Extract” reads the bits back out in order to rebuild the hidden bytes.",
    ],
  },
  crypto: {
    icon: "🔐",
    title: "Lesson 3: What is a cipher, and what does “cracking” mean?",
    body: [
      "Cryptography is the science of scrambling messages so only the intended reader can unscramble them. A cipher is the recipe for scrambling, and the key is the secret setting for that recipe. For example, “shift every letter 3 places” is a cipher, and 3 is the key.",
      "Cracking means recovering the message without being given the key. Old-style ciphers leave fingerprints. In English, E, T and A are far more common than Z or Q, and simple ciphers keep that pattern even while they shuffle the letters. By counting letters (frequency analysis), a computer can test every possible key and keep the one that produces the most English-looking text.",
      "Two things here are not encryption at all. Encoding (like Base64) just rewrites data in a different alphabet, and anyone can reverse it. Hashing is a one-way fingerprint that can't be reversed, only guessed. Spotting which is which is part of the investigator's job.",
    ],
    sampleLabel: "No ciphertext yet? Load a practice one",
    sample: "Gur oynpx obng yrnirf gur uneobe ng zvqavtug. Rirelguvat lbh arrq vf va gur erq obk haqre gur fgnvef.",
  },
  sandbox: {
    lead: "You've watched Sift find a hidden message. Now you'll hide one yourself, using the same technique real criminals and CTF players use. Type a secret, and Sift will tuck it into the lowest bits of a picture's pixels. The picture will look exactly the same. Then switch sides: investigate the picture and pull your own message back out.",
  },
};

// "What's happening right now": a plain-language narrative tied to the
// actual result. Returns null when there's nothing stage-specific to add.
export function narrate(f) {
  if (!f) return null;
  const d = f.data || {};
  switch (f.kind) {
    case "search.results": {
      const m = d.matches || [];
      if (!m.length) return "No pictures matched. Try describing something simpler, like an object or a place.";
      return `Sift placed your words “${d.query}” on its map of meaning and measured the distance to every evidence photo. The closest is ${m[0].filename}, with a similarity of ${(m[0].score * 100).toFixed(1)}%. That number sounds low, but text and photos rarely score above about 35%, so what matters is the ranking. Open the top result in Stage 2 to check it for hidden data.`;
    }
    case "stego.suspicious":
      return "Sift just measured the lowest bit of every colour value in this picture. They look too random: almost exactly half 0s and half 1s, like coin flips. Real photos usually have more pattern than that. It's strong evidence that something was written into those bits. Compare the bit-plane picture with the original, then press “Extract” to try reading the bits back out.";
    case "stego.clean":
      return "Sift measured the lowest bits and they look like ordinary image noise, so there's no strong statistical sign of hiding. Statistics only notice large payloads, though. A short message changes too few pixels to stand out, so a careful investigator still tries extracting before ruling an image out.";
    case "stego.payload": {
      const t = d.text || "";
      const looksB64 = /^[A-Za-z0-9+/=\s]{16,}$/.test(t);
      return `Sift read the last bit of each red, green and blue value in order and joined every 8 bits into a byte. The first 32 bits said how long the message is (${d.length} bytes), and the rest is the message itself.` +
        (looksB64
          ? " The result uses only letters, digits, + and /, which is the signature of Base64 encoding. It still isn't readable, so it was probably encrypted before it was hidden. Send it to Stage 3 to crack it."
          : t ? " It's readable text, so whoever hid it didn't bother encrypting it." : " It's raw binary, which may be a file or encrypted data.");
    }
    case "stego.no_payload":
      return "Sift tried reading the lowest bits as a hidden message, but the length header didn't make sense and the bytes weren't readable. Either nothing is hidden, or it was hidden by a different tool or scrambled with a password.";
    case "crypto.identify":
      return `Before attacking, Sift profiled the text. Its Index of Coincidence (how often two randomly picked letters match) is ${d.stats?.ioc ?? "?"}. English scores about 0.067 and random letters about 0.038. That one number tells us roughly what kind of cipher we're facing.`;
    case "crypto.vigenere": {
      const b = d.best || {};
      const layers = b.layers?.length ? `First it noticed the text was ${b.layers.join(" then ")} encoded and decoded it. That's encoding, not encryption, so it's free to reverse. ` : "";
      return `${layers}The letters underneath were still scrambled, with frequencies flatter than English, which suggests a keyword cipher (Vigenère). Sift tried key lengths until splitting the text into that many columns made each column look like English again. That happened at ${b.key?.length} columns. Each column is just a simple shift, so for each one Sift tried all 26 shifts and kept the one that gave the most E's, T's and A's. Those ${b.key?.length} shifts spell the key “${b.key}”. Message recovered.`;
    }
    case "crypto.caesar":
      return `Every letter had been shifted by the same amount. Sift tried all 25 possible shifts and scored each result by how English its letter counts looked. Shift ${d.best?.key} won by a mile.`;
    case "crypto.xor":
      return `Each byte had been mixed with the same secret number using XOR. There are only 255 possible numbers, so Sift tried them all and kept the one (${d.best?.key}) that produced readable English.`;
    case "crypto.decode":
      return "This was only encoded, not encrypted: the same data written in a different alphabet. Sift recognised the alphabet and reversed it. No key needed.";
    case "crypto.hash-dictionary":
    case "crypto.hash-id":
      return "This is a hash: a fixed-length fingerprint that can't be reversed. The only attack is guessing. Hash likely passwords and see if one produces the same fingerprint.";
    case "crypto.plaintext":
      return "Nothing to crack: this already reads as English. Checking the obvious first is good forensic habit.";
    case "crypto.unbroken":
      return "None of the classic attacks produced English. That usually means modern encryption (like AES), which is designed so that no amount of letter-counting helps without the key.";
    default:
      return null;
  }
}

const RANK = { high: 3, medium: 2, low: 1, info: 0 };

// Pick the most important non-metadata finding to narrate.
export function headline(findings) {
  const pool = (findings || []).filter((f) => f.stage !== "metadata");
  return pool.reduce((best, f) => (!best || RANK[f.severity] > RANK[best.severity] ? f : best), null);
}
