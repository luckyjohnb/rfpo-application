const assimpjs = require('assimpjs');
const fs = require('fs');
const path = require('path');

async function convert() {
    const ajs = await assimpjs();

    // Create file list
    const fileList = new ajs.FileList();
    
    // Read the U3D file
    const u3dData = fs.readFileSync('test_model.u3d');
    fileList.AddFile('model.u3d', new Uint8Array(u3dData));
    
    // Convert to glTF2
    const result = ajs.ConvertFileList(fileList, 'gltf2');
    
    if (!result.IsSuccess()) {
        console.error('Conversion failed:', result.GetErrorCode());
        // Try OBJ format instead
        const result2 = ajs.ConvertFileList(fileList, 'obj');
        if (!result2.IsSuccess()) {
            console.error('OBJ conversion also failed:', result2.GetErrorCode());
            
            // Try STL
            const result3 = ajs.ConvertFileList(fileList, 'stl');
            if (!result3.IsSuccess()) {
                console.error('STL conversion also failed:', result3.GetErrorCode());
                
                // List supported formats
                console.log('\nSupported import formats:');
                // Check if U3D is even supported
                return;
            }
            const fileCount3 = result3.FileCount();
            console.log(`STL Output files: ${fileCount3}`);
            for (let i = 0; i < fileCount3; i++) {
                const fn = result3.GetFileName(i);
                const fd = result3.GetFileContent(i);
                console.log(`  ${fn}: ${fd.length} bytes`);
                fs.writeFileSync(fn, Buffer.from(fd));
            }
            return;
        }
        const fileCount2 = result2.FileCount();
        console.log(`OBJ Output files: ${fileCount2}`);
        for (let i = 0; i < fileCount2; i++) {
            const fn = result2.GetFileName(i);
            const fd = result2.GetFileContent(i);
            console.log(`  ${fn}: ${fd.length} bytes`);
            fs.writeFileSync(fn, Buffer.from(fd));
        }
        return;
    }
    
    // Get output files
    const fileCount = result.FileCount();
    console.log(`Output files: ${fileCount}`);
    
    for (let i = 0; i < fileCount; i++) {
        const fileName = result.GetFileName(i);
        const fileData = result.GetFileContent(i);
        console.log(`  ${fileName}: ${fileData.length} bytes`);
        fs.writeFileSync(fileName, Buffer.from(fileData));
    }
    
    console.log('Done! Files saved.');
}

convert().catch(err => console.error('Error:', err));
