# Company-House-SH01-Parsing

This repository is a supplementary material for the paper *M. Garkavenko et al. "Valuation of Startups: A Machine Learning Perspective." 43rd European Conference on Information Retrieval, Springer, 2021, [https://doi.org/10.1007/978-3-030-72113-8_12](https://doi.org/10.1007/978-3-030-72113-8_12)*.

The UK government generously provides critical financial information about UK startups through a public API. The goal of this project is to streamline the process of extracting funding amounts and company valuations at different funding rounds from SH01 documents. The code accomplishes the following tasks for the companies whose Companies House IDs are listed in `data/companies_house_ids_list.txt`:

* Retrieves the filing history via the Companies House API.
* Downloads all SH01-type documents.
* Uses the Tesseract Open Source OCR Engine to read these documents, extracting the number of shares allotted, share price, and total number of shares. These values are then used to infer the funding amount and company valuation.

## Accuracy

There are different versions of document forms in the database, and the accuracy of our parsing method varies significantly across these different types. Below is an estimated accuracy for each document type:

| Document Type | Errors/Checked Documents |
|---------------|--------------------------|
| Online        | 0/50                     |
| Offline6      | 3/20                     |
| Online_old    | 6/20                     |
| Offline5      | 4/20                     |

This breakdown highlights the varying performance of the parsing method depending on the document type, emphasizing the need for tailored approaches to ensure high accuracy.
