function updateFileName(labelId, fileInputId) {
  var fileInput = document.getElementById(fileInputId);
  var label = document.getElementById(labelId);
  if (fileInput.files.length > 0) {
    label.textContent = fileInput.files[0].name;
  } else {
    label.textContent = "No file chosen";
  }
}
