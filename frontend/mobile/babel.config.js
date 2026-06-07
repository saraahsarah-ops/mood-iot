module.exports = function (api) {
  api.cache(true);
  return {
    presets: ["babel-preset-expo"],
    // react-native-reanimated avait ete declare mais jamais importe dans le
    // code. Le plugin a ete retire (cf. Phase 2.7) pour reduire la taille
    // du build et eviter les problemes CMake/MAX_PATH sous Windows.
  };
};
